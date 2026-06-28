#!/usr/bin/env python3
"""Print a published snapshot's headline straight from S3 for a quick "what is live" check.

With no run id it reports the live pointer (snapshots/latest.json) and the newest agent snapshot, which
is what the landing page renders. Pass a run id to inspect a specific snapshot. AWS credentials come
from the usual chain (set AWS_PROFILE or pass --profile).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

RUN_ID = re.compile(r"(run|agent|live)-(?P<date>\d{8})(-\d{6})?")
AGENT_SNAPSHOT = re.compile(r"snapshots/\d{4}/\d{2}/\d{2}/(agent-\d{8}-\d{6})\.json$")


def _aws(args: list[str], profile: str | None, region: str) -> str:
    cmd = ["aws", *args, "--region", region]
    if profile:
        cmd += ["--profile", profile]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"aws {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _read(bucket: str, key: str, profile: str | None, region: str) -> dict | None:
    out = _aws(["s3", "cp", f"s3://{bucket}/{key}", "-"], profile, region)
    return json.loads(out) if out.strip() else None


def _newest_agent(bucket: str, profile: str | None, region: str) -> str | None:
    listing = _aws(["s3", "ls", f"s3://{bucket}/snapshots/", "--recursive"], profile, region)
    runs = sorted(match.group(1) for line in listing.splitlines() if (match := AGENT_SNAPSHOT.search(line)))
    return runs[-1] if runs else None


def _summarise(label: str, snapshot: dict, top: int) -> None:
    run = snapshot.get("run", {})
    agent = snapshot.get("agent")
    champion = snapshot.get("champion") or {}
    teams = sorted(snapshot.get("teams", []), key=lambda t: -(t.get("champion_prob") or 0))[:top]
    print(f"\n{label}")
    print(f"  run {run.get('run_id')}  kind={run.get('kind')}  as_of={run.get('as_of')}  created={run.get('created_at')}")
    if agent:
        narrative = (agent.get("narrative") or {}).get("headline", "")
        print(
            f"  agent: {len(agent.get('worlds') or [])} worlds, {len(agent.get('camps') or [])} camps, "
            f"{len(agent.get('sources') or [])} sources, {len(agent.get('market_gaps') or [])} market gaps"
        )
        if narrative:
            print(f"  headline: {narrative[:200]}")
    else:
        print("  agent: none (deterministic sim snapshot)")
    if champion.get("blend_weight") is not None:
        print(f"  champion blend_weight: {champion['blend_weight']}")
    top_line = ", ".join(f"{t.get('name')} {round((t.get('champion_prob') or 0) * 100, 1)}%" for t in teams)
    print(f"  top {top}: {top_line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", nargs="?", help="snapshot to inspect; omit for the live pointer and newest agent")
    parser.add_argument("--env", choices=["prod", "dev"], default="prod")
    parser.add_argument("--profile", help="AWS profile (else the default credential chain)")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--top", type=int, default=8, help="how many teams to list (default 8)")
    args = parser.parse_args()
    bucket = f"wolves-superforecaster-{args.env}"

    if args.run_id:
        if not (match := RUN_ID.fullmatch(args.run_id)):
            sys.exit(f"Invalid run id: {args.run_id}")
        day = match.group("date")
        snapshot = _read(bucket, f"snapshots/{day[:4]}/{day[4:6]}/{day[6:8]}/{args.run_id}.json", args.profile, args.region)
        if snapshot is None:
            sys.exit(f"No snapshot {args.run_id}")
        _summarise(args.run_id, snapshot, args.top)
        return

    latest = _read(bucket, "snapshots/latest.json", args.profile, args.region)
    if latest:
        _summarise("live pointer (snapshots/latest.json)", latest, args.top)
    newest = _newest_agent(bucket, args.profile, args.region)
    if newest and newest != (latest or {}).get("run", {}).get("run_id"):
        match = RUN_ID.fullmatch(newest)
        day = match.group("date")
        agent = _read(bucket, f"snapshots/{day[:4]}/{day[4:6]}/{day[6:8]}/{newest}.json", args.profile, args.region)
        if agent:
            _summarise("newest agent forecast (landing headline)", agent, args.top)


if __name__ == "__main__":
    main()
