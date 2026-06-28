#!/usr/bin/env python3
"""Read agent-run decision logs from Logfire for triage.

`runs` lists recent agent runs with their outcome; `show` prints one run's
decision timeline (waves, admissions, node failures, submission result).
Needs LOGFIRE_READ_TOKEN in the environment or in the repo .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUTCOME = {
    "complete": "submitted",
    "degraded": "degraded",
    "failed": "STRANDED",
    "cancelled": "cancelled",
    "started": "running?",
}


def _token() -> str:
    token = os.environ.get("LOGFIRE_READ_TOKEN")
    if token:
        return token
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("LOGFIRE_READ_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("LOGFIRE_READ_TOKEN not set (export it or add it to .env)")


def _endpoint(token: str) -> str:
    parts = token.split("_")
    region = parts[2] if len(parts) > 3 and parts[0] == "pylf" else "us"
    return f"https://logfire-{region}.pydantic.dev/v1/query"


def query(sql: str) -> list[dict]:
    url = _endpoint(TOKEN) + "?" + urllib.parse.urlencode({"sql": sql})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 5:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f"Logfire query failed ({exc.code}): {exc.read().decode()[:200]}")
    columns = [column["name"] for column in data["columns"]]
    values = [column["values"] for column in data["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in zip(*values, strict=True)] if values else []


def _run_id(span_name: str) -> str:
    return span_name.removeprefix("run:")


def cmd_runs(args: argparse.Namespace) -> None:
    window = f"now() - interval '{args.days} days'"
    roots = query(
        "SELECT trace_id, span_name, to_char(start_timestamp,'MM-DD HH24:MI') started, "
        "extract(epoch from start_timestamp) epoch, round(duration::numeric,0) dur "
        f"FROM records WHERE span_name LIKE 'run:agent-%' AND start_timestamp > {window} "
        f"ORDER BY start_timestamp DESC LIMIT {args.limit}"
    )
    if not roots:
        print(f"No agent runs in the last {args.days} days.")
        return
    aggs = {
        row["trace_id"]: row
        for row in query(
            "SELECT trace_id, "
            "sum(case when span_name like 'graph_patch%' then 1 else 0 end) waves, "
            "sum(case when span_name like 'node:%' then 1 else 0 end) nodes, "
            "sum(case when span_name like 'node_error%' then 1 else 0 end) cap_errs, "
            "sum(case when span_name like 'admission%' and attributes->'input'->>'drops' like '%forecast:%' "
            "then 1 else 0 end) fc_drops "
            f"FROM records WHERE start_timestamp > {window} GROUP BY trace_id"
        )
    }
    # live_attempt events are standalone traces, so match the terminal one to the
    # run that started most recently before it; its cost_usd is the run's spend.
    terminals = [
        row
        for row in query(
            "SELECT extract(epoch from start_timestamp) epoch, attributes->'input'->>'status' status, "
            "attributes->'input'->>'cost_usd' cost FROM records WHERE span_name LIKE 'live_attempt%' "
            f"AND attributes->'input'->>'status' <> 'started' AND start_timestamp > {window} "
            "ORDER BY start_timestamp"
        )
    ]
    starts = sorted((float(r["epoch"]), r["trace_id"]) for r in roots)
    final: dict[str, dict] = {}
    for term in terminals:
        prior = [t for t in starts if t[0] <= float(term["epoch"])]
        if prior:
            final[prior[-1][1]] = term

    head = f"{'run':<26}{'start':<12}{'dur':>5}{'wav':>5}{'nodes':>6}{'nErr':>5}{'fcDrop':>7}{'spend$':>8}  outcome"
    print(head)
    print("-" * len(head))
    for root in roots:
        agg = aggs.get(root["trace_id"], {})
        term = final.get(root["trace_id"], {})
        outcome = OUTCOME.get(term.get("status", ""), term.get("status") or "?")
        spend = float(term["cost"]) if term.get("cost") else 0.0
        print(
            f"{_run_id(root['span_name']):<26}{root['started']:<12}{int(root['dur'] or 0):>5}"
            f"{int(agg.get('waves') or 0):>5}{int(agg.get('nodes') or 0):>6}{int(agg.get('cap_errs') or 0):>5}"
            f"{int(agg.get('fc_drops') or 0):>7}{spend:>8.2f}  {outcome}"
        )


def cmd_show(args: argparse.Namespace) -> None:
    run_id = args.run if args.run.startswith("agent-") else f"agent-{args.run}"
    resolved = query(f"SELECT trace_id FROM records WHERE span_name = 'run:{run_id}' LIMIT 1")
    if not resolved:
        sys.exit(f"No run found for {run_id}")
    trace = resolved[0]["trace_id"]
    rows = query(
        "SELECT to_char(start_timestamp,'HH24:MI:SS') t, span_name, level, attributes::text attrs "
        f"FROM records WHERE trace_id = '{trace}' AND (span_name LIKE 'graph_patch%' "
        "OR span_name LIKE 'admission%' OR span_name LIKE 'node%' OR span_name LIKE 'live_attempt%' "
        "OR span_name LIKE 'run_incomplete%' OR span_name LIKE 'revision%') ORDER BY start_timestamp"
    )
    print(f"{run_id}  (trace {trace})\n")
    for row in rows:
        raw = row["attrs"]
        attrs = raw if isinstance(raw, dict) else (json.loads(raw) if raw else {})
        inp = attrs.get("input") or {}
        summary = (attrs.get("output") or {}).get("summary", "") or ""
        name = row["span_name"]
        if name.startswith("graph_patch"):
            kinds = [op.get("kind") for op in (inp.get("ops") or [])]
            detail = f"plan {kinds}  {(inp.get('reason') or '')[:200]}"
        elif name.startswith("admission"):
            detail = f"DROP {inp.get('drops')}"
        elif name.startswith("node_error"):
            detail = f"{inp.get('failure_category')}: {inp.get('error')}"
        elif name.startswith("node:"):
            detail = f"req={inp.get('requests')} {summary[:80]}"
        elif name.startswith("live_attempt"):
            detail = f"status={inp.get('status')}"
        else:
            detail = summary[:120] or json.dumps(inp)[:120]
        print(f"{row['t']}  {name:<30} {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    runs = sub.add_parser("runs", help="list recent agent runs and their outcome")
    runs.add_argument("--days", type=int, default=3, help="look back this many days (default 3)")
    runs.add_argument("--limit", type=int, default=20, help="show at most this many runs (default 20)")
    runs.set_defaults(func=cmd_runs)
    show = sub.add_parser("show", help="print one run's decision timeline")
    show.add_argument("run", help="run id, e.g. agent-20260628-100057 or 20260628-100057")
    show.set_defaults(func=cmd_show)
    args = parser.parse_args()
    args.func(args)


TOKEN = _token()

if __name__ == "__main__":
    main()
