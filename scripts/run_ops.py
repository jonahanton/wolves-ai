#!/usr/bin/env python3
"""Launch, list, and stop engine runs from the CLI by dispatching the GitHub Actions workflows.

`launch` triggers run-engine.yml (daily or agent, with an optional ceiling); `active` and `stop` trigger
admin-control.yml. Each prints the dispatched run's URL; pass --watch to stream it to completion. Needs
the gh CLI authenticated as an account with write access to the repo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

RUN_ENGINE = "run-engine.yml"
ADMIN = "admin-control.yml"


def _gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _newest_run_id(workflow: str) -> int | None:
    out = _gh(["run", "list", "--workflow", workflow, "--limit", "1", "--json", "databaseId"])
    runs = json.loads(out)
    return runs[0]["databaseId"] if runs else None


def _dispatch(workflow: str, inputs: dict[str, str], watch: bool) -> None:
    before = _newest_run_id(workflow)
    args = ["workflow", "run", workflow]
    for key, value in inputs.items():
        args += ["-f", f"{key}={value}"]
    _gh(args)
    run_id = None
    for _ in range(20):
        time.sleep(2)
        run_id = _newest_run_id(workflow)
        if run_id is not None and run_id != before:
            break
    if run_id is None or run_id == before:
        print("Dispatched; the run has not registered yet. Check: gh run list --workflow", workflow)
        return
    url = _gh(["run", "view", str(run_id), "--json", "url"])
    print(f"Dispatched: {json.loads(url)['url']}")
    if watch:
        subprocess.run(["gh", "run", "watch", str(run_id), "--exit-status"])


def cmd_launch(args: argparse.Namespace) -> None:
    inputs = {"mode": args.mode}
    if args.ceiling is not None:
        inputs["ceiling_usd"] = str(args.ceiling)
    if args.force:
        inputs["force"] = "true"
    _dispatch(RUN_ENGINE, inputs, args.watch)


def cmd_active(args: argparse.Namespace) -> None:
    _dispatch(ADMIN, {"action": "active-runs"}, watch=True)


def cmd_stop(args: argparse.Namespace) -> None:
    if args.task:
        _dispatch(ADMIN, {"action": "stop-task", "task_arn": args.task}, watch=True)
    else:
        _dispatch(ADMIN, {"action": "stop-all"}, watch=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("launch", help="dispatch a daily or agent run")
    launch.add_argument("--mode", choices=["agent", "daily"], default="agent")
    launch.add_argument("--ceiling", type=float, help="agent spend ceiling in USD (blank uses the engine default)")
    launch.add_argument("--force", action="store_true", help="skip the active-task guard")
    launch.add_argument("--watch", action="store_true", help="stream the dispatched run to completion")
    launch.set_defaults(func=cmd_launch)
    active = sub.add_parser("active", help="list in-flight engine tasks")
    active.set_defaults(func=cmd_active)
    stop = sub.add_parser("stop", help="stop one task (--task ARN) or all engine tasks")
    stop.add_argument("--task", help="task ARN to stop; omit to stop all")
    stop.set_defaults(func=cmd_stop)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
