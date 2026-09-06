#!/usr/bin/env python3
"""Reproducible micro-benchmarks for the skill's helper scripts.

Measures two things per operation: wall time, and controller-facing stdout
size — the controller agent consumes script output, so output bytes are a
context cost that grows with every call. Standard library only; runs inside
a temporary directory and leaves nothing behind.

Usage:
    python3 benchmarks/bench_scripts.py
"""

from __future__ import annotations

import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def sh(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(f"command failed: {' '.join(args)}")
    return result


def make_tickets(dir_path: Path, n: int, seed: int = 7) -> None:
    rng = random.Random(seed)
    dir_path.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        blockers = (
            [f"{j:03d}" for j in rng.sample(range(1, i), min(rng.randint(0, 2), i - 1))]
            if i > 1
            else []
        )
        (dir_path / f"{i:03d}-ticket.md").write_text(
            f"# {i:03d}: Synthetic outcome {i}\n\n"
            f"**What to build:** Implement synthetic outcome {i} with tests.\n\n"
            f"**Blocked by:** {', '.join(blockers) if blockers else 'None'}\n\n"
            f"**Status:** ready-for-agent\n\n"
            f"**Risk:** medium\n\n"
            f"**Conflict domains:** module{i}\n\n"
            f"## Acceptance criteria\n\n"
            f"- [ ] Outcome {i} works.\n- [ ] Tests cover it.\n",
            encoding="utf-8",
        )


def make_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    sh(["git", "-C", str(path), "init", "-q"])
    sh(["git", "-C", str(path), "config", "user.email", "bench@example.com"])
    sh(["git", "-C", str(path), "config", "user.name", "bench"])
    (path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    sh(["git", "-C", str(path), "add", "."])
    sh(["git", "-C", str(path), "commit", "-qm", "base"])


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    with tempfile.TemporaryDirectory(prefix="tdd-bench-") as temp:
        root = Path(temp)

        for n in (10, 50, 200):
            tickets = root / f"tickets-{n}"
            make_tickets(tickets, n)
            start = time.perf_counter()
            sh(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets),
                "--output", str(root / f"index-{n}.json")])
            rows.append((
                f"index_tickets.py N={n}",
                f"{(time.perf_counter() - start) * 1000:.0f} ms",
                "",
            ))

        # Git-backed operations at N=200: the controller-facing cost profile
        # of a large run (state init, transitions, reconciliation).
        repo = root / "repo"
        make_repo(repo)
        index = root / "index-200.json"
        state = root / "state.json"
        ledger = root / "ledger.md"
        worktree = root / "wt"

        start = time.perf_counter()
        sh(["python3", str(SCRIPTS / "make_worktree.py"),
            "--repo", str(repo), "--path", str(worktree),
            "--branch", "agent/bench/integration",
            "--metadata", str(root / "wt.json")])
        rows.append(("make_worktree.py (create)", f"{(time.perf_counter() - start) * 1000:.0f} ms", ""))

        start = time.perf_counter()
        result = sh(["python3", str(SCRIPTS / "run_state.py"), "init",
                     "--index", str(index), "--state", str(state), "--ledger", str(ledger),
                     "--repo", str(repo), "--base", "HEAD",
                     "--integration-branch", "agent/bench/integration",
                     "--integration-worktree", str(worktree)])
        rows.append((
            "run_state.py init N=200",
            f"{(time.perf_counter() - start) * 1000:.0f} ms",
            f"stdout {len(result.stdout) / 1024:.0f} KiB",
        ))

        def transition(ticket: str, quiet: bool) -> tuple[float, int]:
            args = ["python3", str(SCRIPTS / "run_state.py"), "transition",
                    "--state", str(state), "--ticket", ticket, "--status", "running"]
            if quiet:
                args.append("--quiet")
            start = time.perf_counter()
            out = sh(args)
            return time.perf_counter() - start, len(out.stdout)

        full_times, quiet_times, full_bytes, quiet_bytes = [], [], 0, 0
        for i in range(1, 11):
            elapsed, size = transition(f"{i:03d}", quiet=False)
            full_times.append(elapsed)
            full_bytes += size
        for i in range(11, 21):
            elapsed, size = transition(f"{i:03d}", quiet=True)
            quiet_times.append(elapsed)
            quiet_bytes += size
        rows.append((
            "run_state.py transition full (per call)",
            f"{sum(full_times) / len(full_times) * 1000:.0f} ms",
            f"stdout/call {full_bytes / len(full_times) / 1024:.0f} KiB",
        ))
        rows.append((
            "run_state.py transition --quiet (per call)",
            f"{sum(quiet_times) / len(quiet_times) * 1000:.0f} ms",
            f"stdout/call {quiet_bytes / len(quiet_times) / 1024:.1f} KiB "
            f"({full_bytes // max(quiet_bytes, 1)}x smaller)",
        ))

        result = sh(["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state)])
        full_reconcile = len(result.stdout)
        result = sh(["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state), "--quiet"])
        rows.append((
            "reconcile_run.py full vs --quiet (stdout)",
            "",
            f"full {full_reconcile / 1024:.0f} KiB vs quiet {len(result.stdout) / 1024:.1f} KiB",
        ))

        (worktree / "extra.py").write_text("x = 1\n" * 50, encoding="utf-8")
        sh(["git", "-C", str(worktree), "add", "."])
        sh(["git", "-C", str(worktree), "commit", "-qm", "change"])
        base = sh(["git", "-C", str(worktree), "rev-parse", "HEAD~1"]).stdout.strip()
        head = sh(["git", "-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
        start = time.perf_counter()
        sh(["python3", str(SCRIPTS / "package_diff.py"), "--repo", str(worktree),
            "--base", base, "--head", head, "--ticket", "001",
            "--output", str(root / "diff.md")])
        rows.append(("package_diff.py (small diff)", f"{(time.perf_counter() - start) * 1000:.0f} ms", ""))

    width = max(len(name) for name, _, _ in rows) + 2
    print(f"{'benchmark'.ljust(width)} {'wall time':>14}  {'output size':>34}")
    for name, wall, size in rows:
        print(f"{name.ljust(width)} {wall:>14}  {size:>34}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
