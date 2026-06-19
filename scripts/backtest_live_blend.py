"""Backtest the live shot/possession blend (forecast.py live path).

Two evaluations, because no historical World Cup corpus carries minute-level
shot data yet:

1. Recorded-snapshot replay. Walks runs/live/history and, for any finished
   match whose live snapshots carried shots on target, scores the blended vs
   unblended 90-minute W/D/L forecast by ranked probability score in the final
   phase. Reports honestly when no recorded snapshot has shot data (the current
   state), so the gate is never a misleading pass on an empty sample.

2. Leakage-free synthetic check. The mechanism's claim is "if shots on target
   track the true scoring rate, blending them in corrects a biased pre-match
   lambda and improves late-match calibration". We test exactly that: draw a
   true rate, give the model a biased pre-match anchor, draw shots from the true
   rate (never from the outcome), and compare final-phase RPS with and without
   the blend. A win here means the blend earns its place when shots are
   informative; the magnitude shows the halflife and cap are sensible.

Usage: uv run --project engine python scripts/backtest_live_blend.py [--trials 4000]
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

from wolves.models.inmatch import MatchState, live_win_probabilities
from wolves.models.live_signals import DEFAULT_BLEND, LiveSignals, blend_rates

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY = REPO_ROOT / "runs" / "live" / "history"
FINAL_PHASE_MIN = 72  # last 20% of regulation


def _rps(probs: tuple[float, float, float], outcome: int) -> float:
    observed = np.zeros(3)
    observed[outcome] = 1.0
    cumulative = np.cumsum(np.array(probs) - observed)
    return float(np.sum(cumulative[:2] ** 2) / 2)


def replay_recorded_snapshots() -> None:
    files = sorted(glob.glob(str(HISTORY / "*" / "*.json")))
    with_shots = 0
    for path in files:
        snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
        for fixture in snapshot.get("fixtures", []):
            if fixture.get("home_shots_on") is not None or fixture.get("away_shots_on") is not None:
                with_shots += 1
    print(f"recorded snapshots: {len(files)}, fixture-snapshots carrying shot data: {with_shots}")
    if with_shots == 0:
        print("  no recorded snapshot has shot data yet; real-data calibration cannot be scored.")
        print("  this becomes a live gate once World Cup 2026 matches are recorded with the new feed.")


def synthetic_blend_check(*, trials: int, seed: int = 0) -> bool:
    """True rate hidden from the model; pre-match anchor is biased; shots track
    the true rate. Compare final-phase RPS of blended vs unblended forecasts."""
    rng = np.random.default_rng(seed)
    minute = 75.0
    conversion = DEFAULT_BLEND.conversion_prior
    blended_rps = []
    static_rps = []
    for _ in range(trials):
        true_home = float(rng.uniform(0.6, 2.6))
        true_away = float(rng.uniform(0.6, 2.6))
        # The strength model is imperfect: the pre-match anchor carries a bias.
        bias = rng.normal(0.0, 0.45, size=2)
        anchor_home = float(np.clip(true_home + bias[0], 0.2, 4.0))
        anchor_away = float(np.clip(true_away + bias[1], 0.2, 4.0))
        # Shots on target by `minute`, drawn from the true rate, never the outcome.
        shots_home = int(rng.poisson(true_home / conversion * minute / 90.0))
        shots_away = int(rng.poisson(true_away / conversion * minute / 90.0))
        # Goals so far and the eventual 90-minute outcome, both from the true rate.
        gh = int(rng.poisson(true_home * minute / 90.0))
        ga = int(rng.poisson(true_away * minute / 90.0))
        rest_home = gh + int(rng.poisson(true_home * (90.0 - minute) / 90.0))
        rest_away = ga + int(rng.poisson(true_away * (90.0 - minute) / 90.0))
        outcome = 0 if rest_home > rest_away else (1 if rest_home == rest_away else 2)

        state = MatchState(minute=minute, home_goals=gh, away_goals=ga)
        signals = LiveSignals(home_shots_on=shots_home, away_shots_on=shots_away)
        bh, ba = blend_rates(anchor_home, anchor_away, signals, minute)
        blended = live_win_probabilities(bh, ba, state, knockout=False)
        static = live_win_probabilities(anchor_home, anchor_away, state, knockout=False)
        blended_rps.append(_rps((blended["home"], blended["draw"], blended["away"]), outcome))
        static_rps.append(_rps((static["home"], static["draw"], static["away"]), outcome))

    blended_mean = float(np.mean(blended_rps))
    static_mean = float(np.mean(static_rps))
    improvement = static_mean - blended_mean
    print(f"\nsynthetic final-phase RPS over {trials} trials (lower is better):")
    print(f"  static anchor : {static_mean:.5f}")
    print(f"  blended       : {blended_mean:.5f}")
    print(f"  improvement   : {improvement:+.5f} ({improvement / static_mean * 100:+.1f}%)")
    passed = blended_mean < static_mean
    print("verdict:", "blend improves late-match calibration" if passed else "blend does not help")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    replay_recorded_snapshots()
    synthetic_blend_check(trials=args.trials, seed=args.seed)


if __name__ == "__main__":
    main()
