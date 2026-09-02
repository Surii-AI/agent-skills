#!/usr/bin/env python3
"""Index Markdown tickets into a validated dependency graph.

Supports Matt Pocock-style local tickets and the optional extended fields used by
this skill. Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

FIELD_RE = re.compile(
    r"^\s*\*\*(What to build|Blocked by|Status|Risk|Conflict domains):\*\*\s*(.*)$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[\s*[xX]?\s*\]\s+(.+?)\s*$")
COMPLETED_STATUSES = {"done", "complete", "completed", "integrated", "closed", "implemented", "shipped"}
VALID_RISKS = {"low", "medium", "high"}


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def split_domains(raw: str) -> list[str]:
    if not raw.strip():
        return []
    return [item.strip() for item in re.split(r"[;,]", raw) if item.strip()]


def parse_heading(path: Path, lines: list[str]) -> tuple[str, str]:
    heading = next((m.group(1).strip() for line in lines if (m := HEADING_RE.match(line))), "")
    fallback_id = path.stem.split("-", 1)[0]
    if not heading:
        return fallback_id, path.stem.replace("-", " ").strip()

    match = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.+)$", heading)
    if match:
        return match.group(1), match.group(2).strip()

    return fallback_id, heading


def collect_fields_and_sections(lines: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    fields: dict[str, list[str]] = {}
    sections: dict[str, list[str]] = {}
    active_field: str | None = None
    active_section: str | None = None
    seen_section = False

    for line in lines:
        if HEADING_RE.match(line):
            active_field = None
            active_section = None
            continue

        if section_match := SECTION_RE.match(line):
            seen_section = True
            active_section = normalize_label(section_match.group(1))
            sections.setdefault(active_section, [])
            active_field = None
            continue

        # Only preamble fields (before the first "## " section) describe the ticket itself.
        # Later "**Field:**" lines belong to that section's content — post-hoc audit or
        # evidence sections often reuse field names like Status and must not corrupt them.
        if not seen_section and (field_match := FIELD_RE.match(line)):
            active_field = normalize_label(field_match.group(1))
            fields.setdefault(active_field, [])
            value = field_match.group(2).strip()
            if value:
                fields[active_field].append(value)
            active_section = None
            continue

        if active_field:
            if line.strip() and not CHECKBOX_RE.match(line):
                fields[active_field].append(line.strip())
            elif not line.strip():
                active_field = None

        if active_section is not None:
            sections[active_section].append(line.rstrip())

    flattened = {key: "\n".join(value).strip() for key, value in fields.items()}
    return flattened, sections


def section_text(sections: dict[str, list[str]], *names: str) -> str:
    for name in names:
        key = normalize_label(name)
        if key in sections:
            return "\n".join(sections[key]).strip()
    return ""


def parse_ticket(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    ticket_id, title = parse_heading(path, lines)
    fields, sections = collect_fields_and_sections(lines)

    outcome = fields.get("what to build") or section_text(sections, "What to build")
    blocker_text = fields.get("blocked by") or section_text(sections, "Blocked by")
    raw_status = (fields.get("status") or "ready-for-agent").strip().lower()
    if "\n" in raw_status:
        # Duplicate Status fields (e.g. a post-hoc audit section reusing the field name)
        # flatten into a compound value; use the first component and warn.
        status = next((part.strip() for part in raw_status.splitlines() if part.strip()), "")
    else:
        status = raw_status
    risk = (fields.get("risk") or "").strip().lower() or None
    conflict_domains = split_domains(fields.get("conflict domains", ""))

    acceptance = []
    for line in lines:
        match = CHECKBOX_RE.match(line)
        if match:
            acceptance.append(match.group(1).strip())

    constraints = section_text(sections, "Constraints")
    context_pointers = []
    for line in sections.get("context pointers", []):
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            context_pointers.append(stripped[2:].strip().strip("`"))
    out_of_scope = section_text(sections, "Out of scope")

    errors: list[str] = []
    warnings: list[str] = []
    if status != raw_status:
        warnings.append(f"compound status {raw_status!r}; using first component {status!r}")
    if not ticket_id:
        errors.append("missing ticket id")
    if not title:
        errors.append("missing title")
    if not outcome:
        errors.append("missing 'What to build' outcome")
    if not blocker_text:
        errors.append("missing 'Blocked by' declaration")
    if not acceptance:
        errors.append("missing acceptance criteria checkboxes")
    if risk and risk not in VALID_RISKS:
        warnings.append(f"unrecognized risk '{risk}'; controller must infer conservatively")

    return {
        "id": ticket_id,
        "title": title,
        "path": str(path.resolve()),
        "outcome": outcome,
        "blocker_text": blocker_text,
        "blockers": [],
        "status": status,
        "risk": risk,
        "conflict_domains": conflict_domains,
        "acceptance_criteria": acceptance,
        "constraints": constraints,
        "context_pointers": context_pointers,
        "out_of_scope": out_of_scope,
        "errors": errors,
        "warnings": warnings,
    }


def resolve_blockers(ticket: dict[str, Any], known_ids: list[str]) -> None:
    raw = ticket["blocker_text"].strip()
    if not raw:
        return
    if re.search(r"\bnone\b|can start immediately", raw, re.IGNORECASE):
        ticket["blockers"] = []
        return

    found: list[str] = []
    for known_id in known_ids:
        pattern = rf"(?<![A-Za-z0-9_.-]){re.escape(known_id)}(?![A-Za-z0-9_.-])"
        if re.search(pattern, raw, re.IGNORECASE):
            found.append(known_id)

    if not found:
        ticket["errors"].append(f"could not resolve blocker references from: {raw!r}")
    ticket["blockers"] = found


def topological_order(tickets: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    ids = [ticket["id"] for ticket in tickets]
    known = set(ids)
    indegree = {ticket_id: 0 for ticket_id in ids}
    outgoing: dict[str, list[str]] = {ticket_id: [] for ticket_id in ids}
    graph_errors: list[str] = []

    for ticket in tickets:
        for blocker in ticket["blockers"]:
            if blocker == ticket["id"]:
                graph_errors.append(f"ticket {ticket['id']} blocks itself")
            elif blocker not in known:
                graph_errors.append(f"ticket {ticket['id']} references missing blocker {blocker}")
            else:
                indegree[ticket["id"]] += 1
                outgoing[blocker].append(ticket["id"])

    queue = deque(sorted((ticket_id for ticket_id, degree in indegree.items() if degree == 0)))
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for dependent in sorted(outgoing[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(ids):
        cyclic = sorted(ticket_id for ticket_id, degree in indegree.items() if degree > 0)
        graph_errors.append(f"dependency cycle detected among: {', '.join(cyclic)}")

    return order, graph_errors


def build_index(ticket_dir: Path) -> dict[str, Any]:
    paths = sorted(path for path in ticket_dir.glob("*.md") if path.is_file())
    tickets = [parse_ticket(path) for path in paths]
    ids = [ticket["id"] for ticket in tickets]

    duplicate_ids = sorted({ticket_id for ticket_id in ids if ids.count(ticket_id) > 1})
    for duplicate in duplicate_ids:
        for ticket in tickets:
            if ticket["id"] == duplicate:
                ticket["errors"].append(f"duplicate ticket id {duplicate}")

    unique_ids = list(dict.fromkeys(ids))
    for ticket in tickets:
        resolve_blockers(ticket, unique_ids)

    order, graph_errors = topological_order(tickets)
    completed = {ticket["id"] for ticket in tickets if ticket["status"] in COMPLETED_STATUSES}
    ready = [
        ticket["id"]
        for ticket in tickets
        if ticket["status"] not in COMPLETED_STATUSES
        and all(blocker in completed for blocker in ticket["blockers"])
    ]

    errors = graph_errors + [
        f"{ticket['id']} ({Path(ticket['path']).name}): {error}"
        for ticket in tickets
        for error in ticket["errors"]
    ]
    warnings = [
        f"{ticket['id']} ({Path(ticket['path']).name}): {warning}"
        for ticket in tickets
        for warning in ticket["warnings"]
    ]
    # Source statuses claiming completion are unverified claims: surface every one so the
    # controller consciously reconciles them against the repository instead of silently
    # trusting the status or silently redispatching corroborated work.
    warnings.extend(
        f"{ticket['id']} ({Path(ticket['path']).name}): marked '{ticket['status']}' complete by "
        "source status; reconcile with Git before trusting or skipping"
        for ticket in tickets
        if ticket["status"] in COMPLETED_STATUSES
    )

    return {
        "schema_version": 1,
        "ticket_directory": str(ticket_dir.resolve()),
        "ticket_count": len(tickets),
        "tickets": tickets,
        "topological_order": order,
        "ready_frontier": ready,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket_dir", type=Path, help="Directory containing one Markdown file per ticket")
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()

    if not args.ticket_dir.is_dir():
        parser.error(f"ticket directory does not exist: {args.ticket_dir}")

    result = build_index(args.ticket_dir)
    rendered = json.dumps(result, indent=2, sort_keys=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    if result["errors"]:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for warning in result["warnings"]:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
