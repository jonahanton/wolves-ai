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
import math
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
LIVE = RUNS / "live"
HISTORY = LIVE / "history"
REAL_BACKUP = RUNS / ".live-real"
MARKER = LIVE / ".demo-active"
SEEDED = LIVE / ".demo-history"

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

@dataclass(frozen=True)
class LiveGame:
    match: int
    home_goals: int
    away_goals: int
    minute: int
    home_shots_on: int
    away_shots_on: int
    home_total_shots: int
    away_total_shots: int
    home_possession: float
    poss_phase: float


# Demo in-play games; the demo owns these fully and seeds each a per-minute history.
LIVE_GAMES: tuple[LiveGame, ...] = (
    LiveGame(22, 1, 0, 63, 6, 2, 13, 5, 0.58, 0.0),  # England 1-0 Croatia
    LiveGame(27, 0, 0, 10, 1, 1, 3, 2, 0.46, 1.4),  # Canada 0-0 Qatar
)


def _poss_at(game: LiveGame, minute: int) -> float:
    swing = game.home_possession + 0.12 * math.sin(minute / 6.0 + game.poss_phase) + 0.04 * math.sin(minute / 2.3)
    return round(min(0.74, max(0.30, swing)), 2)


def _shots_at(game: LiveGame, minute: int) -> tuple[int, int, int, int]:
    frac = minute / game.minute if game.minute else 0.0
    return (
        round(game.home_shots_on * frac),
        round(game.away_shots_on * frac),
        round(game.home_total_shots * frac),
        round(game.away_total_shots * frac),
    )


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

    for game in LIVE_GAMES:
        fx = fixtures[game.match]
        fx["status"] = "live"
        fx["home_goals"], fx["away_goals"], fx["minute"] = game.home_goals, game.away_goals, game.minute
        lead = game.home_goals - game.away_goals
        p_home = 0.5 + 0.14 * lead
        fx["forecast"] = {
            "source": "in_match",
            "p_home": round(p_home, 2),
            "p_away": round(0.85 - p_home, 2),
            "p_draw": 0.15,
            "modal_score": f"{game.home_goals}-{game.away_goals}",
        }
        fx["home_shots_on"], fx["away_shots_on"] = game.home_shots_on, game.away_shots_on
        fx["home_total_shots"], fx["away_total_shots"] = game.home_total_shots, game.away_total_shots
        fx["home_possession"] = game.home_possession
        fx["away_possession"] = round(1.0 - game.home_possession, 2)

    state["live_match_count"] = len(LIVE_GAMES)
    state["poll_status"] = "ok"
    state["fetched_at"] = state["generated_at"] = fetched_at
    state["stale_after"] = stale_after
    results["fetched_at"] = fetched_at
    return state, results


def _seed_history(state: dict) -> None:
    """Per-minute history for every live game, so a replay animates each game's
    bars building rather than holding flat."""
    longest = max(game.minute for game in LIVE_GAMES)
    now = datetime.now(UTC)
    written = []
    for minute in range(1, longest + 1):
        snap = json.loads(json.dumps(state))
        for fixture in snap["fixtures"]:
            game = next((g for g in LIVE_GAMES if g.match == fixture["match"]), None)
            if game is None or minute > game.minute:
                continue
            hso, aso, hts, ats = _shots_at(game, minute)
            home_poss = _poss_at(game, minute)
            fixture["minute"] = minute
            fixture["home_shots_on"], fixture["away_shots_on"] = hso, aso
            fixture["home_total_shots"], fixture["away_total_shots"] = hts, ats
            fixture["home_possession"], fixture["away_possession"] = home_poss, round(1.0 - home_poss, 2)
        stamp = now - timedelta(minutes=longest - minute)
        snap["generated_at"] = snap["fetched_at"] = stamp.isoformat(timespec="seconds")
        day = HISTORY / stamp.date().isoformat()
        day.mkdir(parents=True, exist_ok=True)
        path = day / f"{stamp.strftime('%H%M%S')}.json"
        path.write_text(json.dumps(snap, indent=1))
        written.append(str(path.relative_to(RUNS)))
    SEEDED.write_text("\n".join(written))


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
    _seed_history(state)
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
    if SEEDED.exists():
        for line in SEEDED.read_text().splitlines():
            (RUNS / line).unlink(missing_ok=True)
        SEEDED.unlink()
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
