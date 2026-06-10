"""Leave-one-tournament-out backtest of the in-match model.

For each held-out World Cup, team strengths fitted on the remaining
tournaments give both hazard presets identical pre-match lambdas; every match
is then replayed minute by minute and the W/D/L rank probability score of the
90-minute forecast is averaged per 15-minute phase under the incumbent and
the fitted constants.

Usage: uv run --project engine python scripts/backtest_inmatch.py [--cache-dir DIR] [--holdouts 2014 2018 2022]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_inmatch_hazard import DEFAULT_CACHE, fit_strengths, load_tables, regulation_events

from wolves.models.inmatch import FITTED, INCUMBENT, HazardParams, MatchState, final_score_distribution

ERA_START = 1986
PHASES = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")
MID_GAME = (1, 2, 3, 4)


@dataclass(frozen=True)
class MatchReplay:
    lam_home: float
    lam_away: float
    goal_minutes: tuple[tuple[float, bool], ...]
    red_minutes: tuple[tuple[float, bool], ...]
    outcome: int


def event_minutes(df: pd.DataFrame) -> tuple[tuple[float, bool], ...]:
    """(effective minute, is_home) pairs; H1 stoppage events land at 45.5 so
    they enter the state only once the second half is under way."""
    events = []
    for row in df.itertuples():
        minute = float(row.minute)
        if row.minute_stoppage > 0:
            minute = 45.5 if minute <= 45 else 90.5
        events.append((minute, bool(row.home_team)))
    return tuple(sorted(events))


def build_replays(matches: pd.DataFrame, goals: pd.DataFrame, bookings: pd.DataFrame, holdout: int):
    train = matches[matches["year"] != holdout]
    strengths, mu, host = fit_strengths(train, target_year=holdout)
    g = regulation_events(goals)
    reds = regulation_events(bookings[(bookings["red_card"] == 1) | (bookings["second_yellow_card"] == 1)])

    replays = []
    for row in matches[matches["year"] == holdout].itertuples():
        s_home = strengths.get(row.home_team_name, 0.0)
        s_away = strengths.get(row.away_team_name, 0.0)
        diff = s_home - s_away
        lam_home = float(np.exp(mu + diff + host * (row.home_team_name == row.country_name)))
        lam_away = float(np.exp(mu - diff + host * (row.away_team_name == row.country_name)))
        match_goals = g[g["match_id"] == row.match_id]
        match_reds = reds[reds["match_id"] == row.match_id]
        home_total = int(match_goals["home_team"].sum())
        away_total = len(match_goals) - home_total
        outcome = 0 if home_total > away_total else (1 if home_total == away_total else 2)
        replays.append(MatchReplay(lam_home, lam_away, event_minutes(match_goals), event_minutes(match_reds), outcome))
    return replays


def rps(probs: tuple[float, float, float], outcome: int) -> float:
    observed = np.zeros(3)
    observed[outcome] = 1.0
    cumulative = np.cumsum(np.array(probs) - observed)
    return float(np.sum(cumulative[:2] ** 2) / 2)


def state_at(replay: MatchReplay, minute: int) -> MatchState:
    hg = sum(1 for m, home in replay.goal_minutes if m <= minute and home)
    ag = sum(1 for m, home in replay.goal_minutes if m <= minute and not home)
    hr = sum(1 for m, home in replay.red_minutes if m <= minute and home)
    ar = sum(1 for m, home in replay.red_minutes if m <= minute and not home)
    return MatchState(minute=float(minute), home_goals=hg, away_goals=ag, home_reds=hr, away_reds=ar)


def phase_scores(replays: list[MatchReplay], params: HazardParams) -> np.ndarray:
    totals = np.zeros(len(PHASES))
    counts = np.zeros(len(PHASES))
    for replay in replays:
        for minute in range(90):
            dist = final_score_distribution(replay.lam_home, replay.lam_away, state_at(replay, minute), params=params)
            phase = min(minute // 15, len(PHASES) - 1)
            totals[phase] += rps((dist.p_home, dist.p_draw, dist.p_away), replay.outcome)
            counts[phase] += 1
    return totals / counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--holdouts", type=int, nargs="+", default=[2014, 2018, 2022])
    args = parser.parse_args()

    matches, goals, bookings = load_tables(args.cache_dir, era_start=ERA_START)
    per_phase = {"incumbent": [], "fitted": []}
    for holdout in args.holdouts:
        replays = build_replays(matches, goals, bookings, holdout)
        incumbent = phase_scores(replays, INCUMBENT)
        fitted = phase_scores(replays, FITTED)
        per_phase["incumbent"].append(incumbent)
        per_phase["fitted"].append(fitted)
        print(f"\nWC {holdout} ({len(replays)} matches), mean RPS by phase:")
        print(f"  {'phase':<8}{'incumbent':>11}{'fitted':>9}{'delta':>9}")
        for i, phase in enumerate(PHASES):
            print(f"  {phase:<8}{incumbent[i]:>11.5f}{fitted[i]:>9.5f}{fitted[i] - incumbent[i]:>+9.5f}")

    incumbent_all = np.mean(per_phase["incumbent"], axis=0)
    fitted_all = np.mean(per_phase["fitted"], axis=0)
    print("\nall holdouts, mean RPS by phase:")
    print(f"  {'phase':<8}{'incumbent':>11}{'fitted':>9}{'delta':>9}")
    for i, phase in enumerate(PHASES):
        print(f"  {phase:<8}{incumbent_all[i]:>11.5f}{fitted_all[i]:>9.5f}{fitted_all[i] - incumbent_all[i]:>+9.5f}")

    overall_inc = float(incumbent_all.mean())
    overall_fit = float(fitted_all.mean())
    mid_inc = float(incumbent_all[list(MID_GAME)].mean())
    mid_fit = float(fitted_all[list(MID_GAME)].mean())
    print(f"\noverall: incumbent {overall_inc:.5f} vs fitted {overall_fit:.5f} ({overall_fit - overall_inc:+.5f})")
    print(f"minutes 15-75: incumbent {mid_inc:.5f} vs fitted {mid_fit:.5f} ({mid_fit - mid_inc:+.5f})")
    passed = overall_fit <= overall_inc and mid_fit < mid_inc
    print("verdict:", "challenger accepted" if passed else "challenger rejected")


if __name__ == "__main__":
    main()
