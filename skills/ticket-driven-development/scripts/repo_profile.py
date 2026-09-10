#!/usr/bin/env python3
"""Minimal cross-run preflight profile: fingerprint the facts preflight learned.

``new`` records free-form controller data (discovered commands, measured
budgets, inferred domains) alongside sha256 fingerprints of the files those
facts were derived from. ``reuse`` re-hashes those files in a later run: when
none changed, the recorded facts describe the same repository and can be
adopted instead of re-derived.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve(repo: Path, path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo / candidate


def fingerprint(repo: Path, paths: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        try:
            hashes[path] = hashlib.sha256(resolve(repo, path).read_bytes()).hexdigest()
        except OSError as error:
            print(f"error: cannot fingerprint '{path}': {error}", file=sys.stderr)
            raise SystemExit(2)
    return hashes


def load_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"error: cannot read {what}: {error}", file=sys.stderr)
        raise SystemExit(2)


def emit(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    new = subparsers.add_parser("new", help="record a profile with fingerprints")
    new.add_argument("--repo", required=True, type=Path)
    new.add_argument("--data", required=True, type=Path, help="free-form controller JSON to store verbatim")
    new.add_argument("--fingerprint", action="append", required=True, help="file to hash; repeatable")
    new.add_argument("--output", required=True, type=Path, help="profile destination")

    reuse = subparsers.add_parser("reuse", help="check a recorded profile against the current repository")
    reuse.add_argument("--profile", required=True, type=Path)
    reuse.add_argument("--repo", required=True, type=Path)

    args = parser.parse_args()

    if args.command == "new":
        data = load_json(args.data, "data file")
        emit(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "repo_root": str(args.repo.resolve()),
                "fingerprints": fingerprint(args.repo, args.fingerprint),
                "data": data,
            },
            args.output,
        )
        return 0

    profile = load_json(args.profile, "profile")
    if not isinstance(profile, dict) or not isinstance(profile.get("fingerprints"), dict):
        print("error: profile has no fingerprints object", file=sys.stderr)
        return 2
    changed = []
    for path, recorded in profile["fingerprints"].items():
        file_path = resolve(args.repo, path)
        try:
            current = hashlib.sha256(file_path.read_bytes()).hexdigest()
        except OSError:
            current = None
        if current != recorded:
            changed.append(path)
    emit({"reusable": not changed, "changed": changed}, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
