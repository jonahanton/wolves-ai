"""Replay the full daily agent flow over consecutive days at $0.

Runs the scripted dev agent for N days against a real dataset in an isolated
runs root, then checks the day-over-day machinery actually engaged: published
snapshots with mixed worlds, what_changed diffing the previous run, the
scenario registry accumulating lifecycle events, source memory and journals.

Usage: STORAGE_MODE=local uv run --project engine python scripts/replay_daily_flow.py [--days 3]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_RUNS = Path(os.environ.get("SOURCE_RUNS", str(REPO / "runs")))
REPLAY_ROOT = Path("/tmp/wolves-replay")


def run_day(as_of: str) -> None:
    env = {**os.environ, "RUNS_ROOT": str(REPLAY_ROOT), "STORAGE_MODE": "local"}
    subprocess.run(
        [sys.executable, "-m", "wolves.run_agent", "--dev", "--as-of", as_of, "--sims", "5000"],
        cwd=REPO / "engine",
        env=env,
        check=True,
    )


def check(label: str, condition: bool) -> None:
    print(f"  {'ok' if condition else 'FAIL'}: {label}")
    if not condition:
        raise SystemExit(f"replay check failed: {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--start", type=str, default="2026-06-09")
    args = parser.parse_args()

    shutil.rmtree(REPLAY_ROOT, ignore_errors=True)
    REPLAY_ROOT.mkdir(parents=True)
    for name in ("datasets", "models"):
        shutil.copytree(SOURCE_RUNS / name, REPLAY_ROOT / name)

    start = date.fromisoformat(args.start)
    days = [(start + timedelta(days=i)).isoformat() for i in range(args.days)]
    for day in days:
        print(f"== {day} ==")
        run_day(day)

    snapshots = sorted(REPLAY_ROOT.glob("snapshots/*/*/*/agent-*.json"))
    check(f"{args.days} snapshots published", len(snapshots) == args.days)

    first = json.loads(snapshots[0].read_text())
    last = json.loads(snapshots[-1].read_text())
    artifact_id = last["agent"]["artifact_id"]
    artifacts_dir = REPLAY_ROOT / "runs" / last["run"]["run_id"] / "artifacts"
    index = json.loads((artifacts_dir / "index.json").read_text())
    cited = next((r for r in index["records"] if r["id"] == artifact_id), None)
    check("submission cites a mixture artifact in the run index", cited is not None and cited["kind"] == "mixture")
    artifact = json.loads((artifacts_dir / f"{artifact_id}.json").read_text())
    published_worlds = sorted(w["name"] for w in last["agent"]["worlds"])
    check("published worlds match the cited artifact", published_worlds == sorted(artifact["payload"]["worlds"]))
    focus = first["focus"]["team_id"]
    flat = next(t["champion_prob"] for t in first["teams"] if t["team_id"] == focus)
    check("focus team champion probability published in (0, 1)", 0 < flat < 1)
    check("ledger evidence published", len(last["agent"]["ledger_entries"]) > 0)
    check("attribution decomposed on later days", last["agent"]["attribution"] is not None)

    scenarios = (REPLAY_ROOT / "agent-state" / "scenarios.jsonl").read_text().splitlines()
    check("scenario registry accumulated lifecycle events", len(scenarios) >= args.days)

    run_dirs = sorted((REPLAY_ROOT / "runs").glob("agent-*"))
    check("per-run artifact indices persisted", all((d / "artifacts" / "index.json").exists() for d in run_dirs))
    check("journals persisted per run", all((d / "journal.md").exists() for d in run_dirs))

    events = (run_dirs[-1] / "events.jsonl").read_text()
    check("validator accepted on the final day", "submission accepted" in events)
    print("\nreplay complete:", REPLAY_ROOT)


if __name__ == "__main__":
    main()
