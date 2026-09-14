#!/usr/bin/env python3
"""Re-sync already-installed copies of this skill after `pnpm dlx skills update`.

`skills update` (vercel-labs/skills) never touches omp's skill directories, so
an omp install made by install_skill.py goes stale. Run this afterwards to
force-reinstall over each existing omp install (user scope, plus project scope
when .omp/skills exists). Targets without an existing install are skipped so
the wrapper never creates one implicitly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import install_skill


def main() -> int:
    source = Path(__file__).resolve().parents[1]
    omp = install_skill.TARGETS["omp"]
    project = Path.cwd().resolve()

    destinations = [install_skill.default_destination("omp", "user", project)]
    project_base = project / omp["project"]
    if project_base.parent.exists():
        destinations.append(project_base / install_skill.SKILL_NAME)

    failures = 0
    for destination in destinations:
        if not destination.exists():
            print(f"skip (not installed): {destination}")
            continue
        try:
            installed = install_skill.install(source, destination, "omp", force=True)
        except (OSError, RuntimeError) as exc:
            print(f"ERROR: {destination}: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"updated: {installed}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
