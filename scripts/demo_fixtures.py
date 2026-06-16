"""Load saved demo live fixtures into runs/live, refreshing the freshness window.

The demo state is captured once into runs/demo/ (gitignored). Loading it stamps
a fresh fetched_at/stale_after so the held live game is not treated as stale, then
copies it over runs/live/. Driven by `make demo/on`; pair with JOBS_ENABLED=false
so the poller does not overwrite the fixtures.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
DEMO = RUNS / "demo"
LIVE = RUNS / "live"

# Long window so the demo live game never lapses into the stale branch mid-session.
FRESH_WINDOW = timedelta(days=3650)


def _refresh_freshness(state: dict) -> dict:
    now = datetime.now(UTC)
    stamp = now.isoformat(timespec="seconds")
    state["fetched_at"] = stamp
    state["generated_at"] = stamp
    state["stale_after"] = (now + FRESH_WINDOW).isoformat(timespec="seconds")
    state["poll_status"] = "ok"
    return state


def main() -> int:
    if not (DEMO / "state.json").exists():
        print("no demo fixtures saved at runs/demo/; nothing to load", file=sys.stderr)
        return 1
    LIVE.mkdir(parents=True, exist_ok=True)
    state = json.loads((DEMO / "state.json").read_text())
    (LIVE / "state.json").write_text(json.dumps(_refresh_freshness(state), indent=1))
    shutil.copyfile(DEMO / "results.json", LIVE / "results.json")
    print("demo fixtures loaded into runs/live (freshness refreshed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
