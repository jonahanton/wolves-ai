"""Toggle a synthetic live scenario over the real runs/live data.

The scenario is defined inline: a set of finished results plus one in-play game,
applied to the matches as they exist in the real schedule. `on` backs up the real
live state (once), then writes the scenario with a refreshed freshness window so
the held live game is not treated as stale. `off` restores the real state and
removes the backup.

Driven by `make demo/on` / `make demo/off`, which also flip JOBS_ENABLED so the
poller cannot overwrite the scenario while it is live.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
LIVE = RUNS / "live"
REAL_BACKUP = RUNS / ".live-real"
MARKER = LIVE / ".demo-active"

FILES = ("state.json", "results.json")

# Long window so the demo live game never lapses into the stale branch mid-session.
FRESH_WINDOW = timedelta(days=3650)

# Finished results since the last full forecast: match -> (home_goals, away_goals).
# Mixed directions exercise both upward and downward exit-distribution shifts.
FINISHED: dict[int, tuple[int, int]] = {
    17: (3, 0),  # France beat Senegal: strong upward shift
    19: (0, 2),  # Argentina lose to Algeria: downward shift
    23: (2, 1),  # Portugal edge Congo DR: modest upward shift
}

# One in-play game for the score-hold leg: match -> (home_goals, away_goals, minute).
LIVE_GAME: tuple[int, int, int, int] = (22, 1, 0, 63)  # England 1-0 Croatia, 63'


def _winner(home_goals: int, away_goals: int) -> str | None:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return None


def _now_stamp() -> tuple[str, str]:
    now = datetime.now(UTC)
    return now.isoformat(timespec="seconds"), (now + FRESH_WINDOW).isoformat(timespec="seconds")


def _build_scenario(state: dict, results: dict) -> tuple[dict, dict]:
    fetched_at, stale_after = _now_stamp()
    fixtures = {f["match"]: f for f in state["fixtures"]}

    for match, (hg, ag) in FINISHED.items():
        fx = fixtures[match]
        fx["status"] = "finished"
        fx["home_goals"], fx["away_goals"], fx["minute"] = hg, ag, None
        won = _winner(hg, ag)
        fx["forecast"] = {
            "source": "settled",
            "p_home": 1.0 if won == "home" else 0.0,
            "p_away": 1.0 if won == "away" else 0.0,
            "p_draw": 1.0 if won is None else 0.0,
            "modal_score": f"{hg}-{ag}",
        }
        results["results"][str(match)] = {"match": match, "home_goals": hg, "away_goals": ag, "winner": won}

    lm, lhg, lag, minute = LIVE_GAME
    live_fx = fixtures[lm]
    live_fx["status"] = "live"
    live_fx["home_goals"], live_fx["away_goals"], live_fx["minute"] = lhg, lag, minute
    live_fx["forecast"] = {"source": "in_match", "p_home": 0.78, "p_away": 0.07, "p_draw": 0.15, "modal_score": f"{lhg}-{lag}"}
    live_fx["home_shots_on"], live_fx["away_shots_on"] = 6, 2
    live_fx["home_total_shots"], live_fx["away_total_shots"] = 13, 5
    live_fx["home_possession"], live_fx["away_possession"] = 0.58, 0.42

    state["live_match_count"] = 1
    state["poll_status"] = "ok"
    state["fetched_at"] = state["generated_at"] = fetched_at
    state["stale_after"] = stale_after
    results["fetched_at"] = fetched_at
    return state, results


def _copy(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if (src / name).exists():
            shutil.copyfile(src / name, dst / name)


def demo_on() -> int:
    if not (LIVE / "state.json").exists():
        print("no runs/live state yet; start the stack first", file=sys.stderr)
        return 1
    if not MARKER.exists():
        _copy(LIVE, REAL_BACKUP)
        print("backed up real live state to runs/.live-real/")
    state, results = _build_scenario(
        json.loads((LIVE / "state.json").read_text()),
        json.loads((LIVE / "results.json").read_text()),
    )
    (LIVE / "state.json").write_text(json.dumps(state, indent=1))
    (LIVE / "results.json").write_text(json.dumps(results, indent=1))
    MARKER.write_text("")
    print("demo scenario written to runs/live")
    return 0


def demo_off() -> int:
    if not MARKER.exists():
        print("demo not active; runs/live left unchanged")
        return 0
    if not (REAL_BACKUP / "state.json").exists():
        print("no real backup found at runs/.live-real/; cannot restore", file=sys.stderr)
        return 1
    _copy(REAL_BACKUP, LIVE)
    shutil.rmtree(REAL_BACKUP)
    MARKER.unlink()
    print("real live state restored; demo artefacts removed")
    return 0


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "on":
        return demo_on()
    if action == "off":
        return demo_off()
    print("usage: demo_fixtures.py {on|off}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
