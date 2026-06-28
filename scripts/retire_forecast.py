#!/usr/bin/env python3
"""Retire a published forecast to the backup prefix so the app falls back to the previous one.

Identify the forecast by run id, --latest (the most recent agent forecast), or --date YYYY-MM-DD (the
latest agent forecast that day). Moves snapshots/<date>/<run-id>.* (the snapshot and its sidecars) to
snapshots-backup/<date>/ in the prod or dev bucket; the app then serves the next-newest agent snapshot.
Pass --with-run-dir to also move the raw runs/<run-id>/ directory to runs-backup/. AWS credentials come
from the usual chain (set AWS_PROFILE or pass --profile).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

RUN_ID = re.compile(r"(?P<kind>run|agent|live)-(?P<date>\d{8})(?:-\d{6})?")
AGENT_SNAPSHOT = re.compile(r"snapshots/\d{4}/\d{2}/\d{2}/(agent-\d{8}-\d{6})\.json$")


def _aws(args: list[str], profile: str | None, region: str) -> str:
    cmd = ["aws", *args, "--region", region]
    if profile:
        cmd += ["--profile", profile]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"aws {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _date_path(run_id: str) -> str:
    day = RUN_ID.fullmatch(run_id)["date"]
    return f"{day[:4]}/{day[4:6]}/{day[6:8]}"


def _move(bucket: str, src: str, dst: str, include: str, profile: str | None, region: str, dry_run: bool) -> None:
    args = ["s3", "mv", f"s3://{bucket}/{src}", f"s3://{bucket}/{dst}", "--recursive", "--exclude", "*", "--include", include]
    if dry_run:
        args.append("--dryrun")
    print(_aws(args, profile, region).strip() or "(nothing moved)")


def _agent_runs(bucket: str, profile: str | None, region: str, *, day_path: str | None = None) -> list[str]:
    prefix = f"snapshots/{day_path}/" if day_path else "snapshots/"
    listing = _aws(["s3", "ls", f"s3://{bucket}/{prefix}", "--recursive"], profile, region)
    return sorted(match.group(1) for line in listing.splitlines() if (match := AGENT_SNAPSHOT.search(line)))


def _resolve_run_id(args: argparse.Namespace, bucket: str) -> str:
    if args.run_id:
        if not RUN_ID.fullmatch(args.run_id):
            sys.exit(f"Invalid run id: {args.run_id}")
        return args.run_id
    day_path = None
    if args.date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
            sys.exit(f"Invalid date: {args.date} (expected YYYY-MM-DD)")
        day_path = args.date.replace("-", "/")
    runs = _agent_runs(bucket, args.profile, args.region, day_path=day_path)
    if not runs:
        sys.exit(f"No agent forecast found{f' on {args.date}' if args.date else ''}")
    return runs[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("run_id", nargs="?", help="forecast to retire, e.g. agent-20260626-141147")
    target.add_argument("--latest", action="store_true", help="retire the most recent agent forecast")
    target.add_argument("--date", help="retire the latest agent forecast on this day (YYYY-MM-DD)")
    parser.add_argument("--env", choices=["prod", "dev"], default="prod", help="target bucket (default prod)")
    parser.add_argument("--profile", help="AWS profile (else the default credential chain)")
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--with-run-dir", action="store_true", help="also move runs/<run-id>/ to runs-backup/")
    parser.add_argument("--dry-run", action="store_true", help="show what would move without moving it")
    args = parser.parse_args()

    bucket = f"wolves-superforecaster-{args.env}"
    run_id = _resolve_run_id(args, bucket)
    date = _date_path(run_id)

    listing = _aws(["s3", "ls", f"s3://{bucket}/snapshots/{date}/"], args.profile, args.region)
    if not any(run_id in line for line in listing.splitlines()):
        sys.exit(f"No snapshot {run_id} under s3://{bucket}/snapshots/{date}/")

    print(f"Retiring {run_id} in {bucket}{' (dry run)' if args.dry_run else ''}:")
    _move(bucket, f"snapshots/{date}/", f"snapshots-backup/{date}/", f"{run_id}.*", args.profile, args.region, args.dry_run)
    if args.with_run_dir:
        _move(bucket, f"runs/{run_id}/", f"runs-backup/{run_id}/", "*", args.profile, args.region, args.dry_run)

    if not args.dry_run:
        remaining = _agent_runs(bucket, args.profile, args.region)
        newest = remaining[-1] if remaining else None
        print(f"App will now serve agent forecast: {newest or '(none left; falls back to the daily sim snapshot)'}")


if __name__ == "__main__":
    main()
