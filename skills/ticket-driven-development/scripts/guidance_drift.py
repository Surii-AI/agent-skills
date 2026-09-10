#!/usr/bin/env python3
"""Material-drift gate for senior guidance pinned to a base SHA.

Compares the base a guidance document was pinned to with the actual base the
junior implementer will start from. A moved base regenerates the plan only on
material drift: changed paths that touch a path the guidance names or a
conflict-domain glob. Immaterial drift (docs, unrelated trees) keeps the plan
valid, and ``--patch-base`` re-pins it to the actual base.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

BASE_LINE_RE = re.compile(r"^Base:\s*([0-9a-f]{7,40})\s*$", re.MULTILINE)
NAMED_PATH_RE = re.compile(r"`([^`]+)`")


def git_changed_paths(repo: Path, guidance_base: str, actual_base: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{guidance_base}..{actual_base}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip() or result.stdout.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def path_contains(outer: str, inner: str) -> bool:
    """True when ``inner`` is ``outer`` itself or lives below it (component-wise)."""
    return inner == outer or inner.startswith(outer + "/")


def domain_matches(changed_path: str, glob: str) -> bool:
    if fnmatch(changed_path, glob):
        return True
    # A glob prefix such as `src/apps/api/**` also brands every path below its
    # base directory; a plain `src/apps/api` domain does the same.
    base = glob[: -len("/**")] if glob.endswith("/**") else glob[: -len("/*")] if glob.endswith("/*") else None
    return base is not None and path_contains(base, changed_path)


def stale_changed_paths(changed: list[str], named: list[str], domains: list[str]) -> list[str]:
    stale = []
    for changed_path in changed:
        if any(path_contains(path, changed_path) or path_contains(changed_path, path) for path in named):
            stale.append(changed_path)
        elif any(domain_matches(changed_path, glob) for glob in domains):
            stale.append(changed_path)
    return stale


def emit(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="workspace the bases refer to")
    parser.add_argument("--guidance", required=True, type=Path, help="guidance document to inspect")
    parser.add_argument("--actual-base", required=True, help="SHA the implementer will actually start from")
    parser.add_argument("--domain", action="append", default=[], help="ticket conflict-domain glob; repeatable")
    parser.add_argument("--patch-base", action="store_true", help="re-pin the Base line when the plan is still valid")
    parser.add_argument("--output", type=Path, help="write the verdict JSON here instead of stdout")
    args = parser.parse_args()

    try:
        text = args.guidance.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: cannot read guidance: {error}", file=sys.stderr)
        return 2
    base_match = BASE_LINE_RE.search(text)
    if not base_match:
        emit(
            {"guidance": str(args.guidance), "guidance_base": None, "actual_base": args.actual_base,
             "changed_path_count": 0, "stale_paths": [], "regenerate": True, "reason": "no valid Base line"},
            args.output,
        )
        return 2
    guidance_base = base_match.group(1)

    named = [token for token in NAMED_PATH_RE.findall(text) if "/" in token]
    try:
        changed = git_changed_paths(args.repo, guidance_base, args.actual_base)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not changed:
        regenerate, stale, reason = False, [], "no changed paths between the guidance base and the actual base"
    elif not named and not args.domain:
        regenerate, stale = True, list(changed)
        reason = "guidance names no paths and no domains given; treating any drift as material"
    else:
        stale = stale_changed_paths(changed, named, args.domain)
        regenerate = bool(stale)
        reason = (
            f"material drift: {len(stale)} changed path(s) touch named paths or conflict domains"
            if regenerate
            else "changed paths do not touch named paths or conflict domains"
        )

    if args.patch_base and not regenerate:
        patched = BASE_LINE_RE.sub(f"Base: {args.actual_base}", text)
        if patched != text:
            temp = args.guidance.with_suffix(args.guidance.suffix + ".tmp")
            temp.write_text(patched, encoding="utf-8")
            os.replace(temp, args.guidance)

    emit(
        {
            "guidance": str(args.guidance),
            "guidance_base": guidance_base,
            "actual_base": args.actual_base,
            "changed_path_count": len(changed),
            "stale_paths": stale,
            "regenerate": regenerate,
            "reason": reason,
        },
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
