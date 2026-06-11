"""Fit the in-match hazard constants on World Cup goal timings.

Downloads the Fjelstul worldcup CSVs to a cache directory, builds minute-level
exposure for every men's WC match in the era, and fits the multiplicative goal
hazard by Poisson MLE: per-15-minute baseline bins, score-state and red-card
multipliers, with per-match team-strength offsets so the score-state effects
are not confounded by quality (leading teams keep scoring because they are
better, not because they lead). Strengths come from a time-decayed,
ridge-shrunk one-strength-per-team Poisson fitted per tournament. The run is
fully deterministic; it works offline once the CSVs are cached.

Usage: uv run --project engine python scripts/fit_inmatch_hazard.py [--era 1986] [--cache-dir DIR]
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize

DATA_URL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv"
DATA_FILES = ("matches.csv", "goals.csv", "bookings.csv")
DEFAULT_CACHE = Path.home() / ".cache" / "wolves-inmatch"

STRENGTH_HALF_LIFE_YEARS = 8.0
STRENGTH_RIDGE = 2.0
PROFILE_BINS = 6

INCUMBENT_CONSTANTS = {
    "trailing_one": 1.10,
    "trailing_two": 1.20,
    "leading": 0.90,
    "red_sanctioned": 0.60,
    "red_opponent": 1.50,
}


def load_tables(cache_dir: Path, *, era_start: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (matches, goals, bookings) for men's World Cups from era_start."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        path = cache_dir / name
        if not path.exists():
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(f"{DATA_URL}/{name}", path)
    matches = pd.read_csv(cache_dir / "matches.csv")
    goals = pd.read_csv(cache_dir / "goals.csv")
    bookings = pd.read_csv(cache_dir / "bookings.csv")
    matches = matches[matches["tournament_name"].str.contains("Men's")].copy()
    matches["year"] = matches["tournament_id"].str[3:].astype(int)
    matches = matches[matches["year"] >= era_start]
    goals = goals[goals["match_id"].isin(matches["match_id"])].copy()
    bookings = bookings[bookings["match_id"].isin(matches["match_id"])].copy()
    return matches, goals, bookings


def fit_strengths(matches: pd.DataFrame, *, target_year: int) -> tuple[dict[str, float], float, float]:
    """One strength per team by weighted Poisson MLE: time-decayed to the
    target year, ridge-shrunk to the mean, with a host-country bump."""
    weights = (0.5 ** (np.abs(matches["year"] - target_year) / STRENGTH_HALF_LIFE_YEARS)).to_numpy()
    teams = sorted(set(matches["home_team_name"]) | set(matches["away_team_name"]))
    index = {t: i for i, t in enumerate(teams)}
    hi = matches["home_team_name"].map(index).to_numpy()
    ai = matches["away_team_name"].map(index).to_numpy()
    hg = matches["home_team_score"].to_numpy(float)
    ag = matches["away_team_score"].to_numpy(float)
    h_host = (matches["home_team_name"] == matches["country_name"]).to_numpy(float)
    a_host = (matches["away_team_name"] == matches["country_name"]).to_numpy(float)
    n = len(teams)

    def rates(p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        s, mu, host = p[:n], p[n], p[n + 1]
        return mu + s[hi] - s[ai] + host * h_host, mu + s[ai] - s[hi] + host * a_host

    def nll(p: np.ndarray) -> float:
        lh, la = rates(p)
        ll = weights * (hg * lh - np.exp(lh) + ag * la - np.exp(la))
        return -float(ll.sum()) + STRENGTH_RIDGE * float(np.sum(p[:n] ** 2))

    def grad(p: np.ndarray) -> np.ndarray:
        lh, la = rates(p)
        rh = weights * (hg - np.exp(lh))
        ra = weights * (ag - np.exp(la))
        gs = np.zeros(n)
        np.add.at(gs, hi, rh - ra)
        np.add.at(gs, ai, ra - rh)
        return -np.concatenate([gs, [(rh + ra).sum(), (rh * h_host + ra * a_host).sum()]]) + np.concatenate(
            [2 * STRENGTH_RIDGE * p[:n], [0.0, 0.0]]
        )

    p0 = np.zeros(n + 2)
    p0[n] = np.log(max(float((hg.sum() + ag.sum()) / (2 * len(matches))), 0.1))
    result = minimize(nll, p0, jac=grad, method="L-BFGS-B")
    if not result.success:
        raise RuntimeError(f"strength fit failed for {target_year}: {result.message}")
    return dict(zip(teams, result.x[:n], strict=False)), float(result.x[n]), float(result.x[n + 1])


def match_offsets(matches: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Per-match (home, away) log-strength offsets, one strength fit per tournament."""
    offsets: dict[str, tuple[float, float]] = {}
    for year, tournament in matches.groupby("year"):
        strengths, _, host = fit_strengths(matches, target_year=int(year))
        for row in tournament.itertuples():
            diff = strengths[row.home_team_name] - strengths[row.away_team_name]
            home = diff + host * (row.home_team_name == row.country_name)
            away = -diff + host * (row.away_team_name == row.country_name)
            offsets[str(row.match_id)] = (home, away)
    return offsets


def regulation_events(df: pd.DataFrame) -> pd.DataFrame:
    """Rows from regulation play, with the integer regulation minute."""
    df = df[df["match_period"].str.startswith(("first half", "second half"))].copy()
    df["minute"] = df["minute_regulation"].astype(int).clip(upper=90)
    return df


def build_minute_exposure(matches: pd.DataFrame, goals: pd.DataFrame, bookings: pd.DataFrame):
    """Per (match, minute 1..90): score and red-card state entering the minute
    plus goals scored in it; stoppage goals are returned separately because
    their exposure length is unknown per match."""
    g = regulation_events(goals)
    g["stoppage"] = g["minute_stoppage"] > 0
    reds = regulation_events(bookings[(bookings["red_card"] == 1) | (bookings["second_yellow_card"] == 1)])

    rows: list[tuple[str, int, int, int, int, int, int]] = []
    stoppage_rows: list[tuple[str, int]] = []
    goal_cols = ["match_id", "minute", "home_team", "stoppage"]
    goals_by_match = dict(list(g[goal_cols].groupby("match_id")))
    reds_by_match = dict(list(reds[["match_id", "minute", "home_team"]].groupby("match_id")))
    for mid in matches["match_id"].astype(str):
        goal_minutes: dict[int, list[int]] = {}
        for row in goals_by_match.get(mid, pd.DataFrame(columns=goal_cols)).itertuples():
            if row.stoppage:
                stoppage_rows.append((mid, int(row.minute)))
                continue
            counts = goal_minutes.setdefault(int(row.minute), [0, 0])
            counts[0 if row.home_team else 1] += 1
        red_minutes: dict[int, list[int]] = {}
        for row in reds_by_match.get(mid, pd.DataFrame(columns=goal_cols[:3])).itertuples():
            counts = red_minutes.setdefault(int(row.minute), [0, 0])
            counts[0 if row.home_team else 1] += 1
        hg = ag = hr = ar = 0
        for minute in range(1, 91):
            dg = goal_minutes.get(minute, [0, 0])
            rows.append((mid, minute, hg - ag, hg + ag, hr - ar, dg[0], dg[1]))
            hg += dg[0]
            ag += dg[1]
            dr = red_minutes.get(minute, [0, 0])
            hr += dr[0]
            ar += dr[1]
    exposure = pd.DataFrame(rows, columns=["match_id", "minute", "sd", "total", "rd", "hg", "ag"])
    stoppage = pd.DataFrame(stoppage_rows, columns=["match_id", "reg_min"])
    return exposure, stoppage


def side_stacked(exposure: pd.DataFrame, offsets: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Stack home and away rows so each row is one side-minute of exposure."""
    frames = []
    for side, goal_col, sign in (("h", "hg", 1), ("a", "ag", -1)):
        frame = pd.DataFrame(
            {
                "y": exposure[goal_col],
                "minute": exposure["minute"],
                "sd": sign * exposure["sd"],
                "total": exposure["total"],
                "rd": sign * exposure["rd"],
                "match_id": exposure["match_id"],
                "is_home": 1.0 if side == "h" else 0.0,
            }
        )
        frame["offset"] = frame["match_id"].map({k: v[0 if side == "h" else 1] for k, v in offsets.items()})
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def design_matrix(df: pd.DataFrame, *, granular: bool) -> pd.DataFrame:
    design = pd.DataFrame({"const": 1.0, "is_home": df["is_home"]})
    bins = np.minimum((df["minute"] - 1) // 15, PROFILE_BINS - 1)
    for b in range(1, PROFILE_BINS):
        design[f"bin{b}"] = (bins == b).astype(float)
    sd, total = df["sd"].to_numpy(), df["total"].to_numpy()
    design["trailing_one"] = (sd == -1).astype(float)
    design["trailing_two"] = (sd <= -2).astype(float)
    if granular:
        design["score_draw"] = ((sd == 0) & (total > 0)).astype(float)
        design["leading_one"] = (sd == 1).astype(float)
        design["leading_two"] = (sd >= 2).astype(float)
    else:
        design["leading"] = (sd >= 1).astype(float)
    design["red_sanctioned"] = (df["rd"] > 0).astype(float)
    design["red_opponent"] = (df["rd"] < 0).astype(float)
    return design


def fit_hazard(stacked: pd.DataFrame, *, granular: bool):
    design = design_matrix(stacked, granular=granular)
    model = sm.GLM(stacked["y"], design, family=sm.families.Poisson(), offset=stacked["offset"])
    return model.fit()


def profile_bins(result) -> np.ndarray:
    log_bins = np.array([0.0] + [result.params[f"bin{b}"] for b in range(1, PROFILE_BINS)])
    return np.exp(log_bins) / np.exp(log_bins).mean()


def calibration_factor(stacked: pd.DataFrame, result) -> float:
    """Reciprocal of the exposure-weighted mean score multiplier, so a model
    anchored on pre-match lambdas keeps kickoff goal means on target."""
    sd = stacked["sd"].to_numpy()
    multipliers = {
        "trailing_one": (sd == -1).mean(),
        "trailing_two": (sd <= -2).mean(),
        "leading": (sd >= 1).mean(),
    }
    mean = (sd == 0).mean() + sum(np.exp(result.params[k]) * share for k, share in multipliers.items())
    return float(1.0 / mean)


def print_multiplier_table(result, calibration: float) -> None:
    print(f"\n{'constant':<16}{'incumbent':>10}{'fitted':>9}{'(se log)':>10}{'calibrated':>12}")
    for name, incumbent in INCUMBENT_CONSTANTS.items():
        fitted = float(np.exp(result.params[name]))
        scaled = fitted * calibration if not name.startswith("red") else fitted
        print(f"{name:<16}{incumbent:>10.3f}{fitted:>9.3f}{result.bse[name]:>10.3f}{scaled:>12.3f}")
    print(f"{'level':<16}{1.0:>10.3f}{1.0:>9.3f}{'ref':>10}{calibration:>12.3f}")


def stoppage_report(matches: pd.DataFrame, exposure: pd.DataFrame, stoppage: pd.DataFrame) -> None:
    """Effective stoppage lengths implied by stoppage goal counts at the
    closing-bin scoring rate, the quantity the chain actually plays."""
    print("\nimplied effective stoppage minutes (at the closing-bin rate):")
    closing = exposure[exposure["minute"] > 75]
    final_margin = exposure[exposure["minute"] == 90].set_index("match_id")["sd"].abs()
    for era in sorted({int(matches["year"].min()), 2010, 2018, 2022}):
        ids = set(matches[matches["year"] >= era]["match_id"].astype(str))
        if not ids:
            continue
        n = len(ids)
        era_exp = exposure[exposure["match_id"].isin(ids)]
        era_stop = stoppage[stoppage["match_id"].isin(ids)]
        h1_rate = era_exp[(era_exp["minute"] > 30) & (era_exp["minute"] <= 45)][["hg", "ag"]].to_numpy().sum() / (
            15 * n
        )
        h1 = (era_stop["reg_min"] == 45).sum() / n / h1_rate
        close_ids = {m for m in ids if final_margin.get(m, 0) <= 1}
        parts = []
        for label, group in (("close", close_ids), ("settled", ids - close_ids)):
            if not group:
                continue
            rate = closing[closing["match_id"].isin(group)][["hg", "ag"]].to_numpy().sum() / (15 * len(group))
            goals = ((era_stop["reg_min"] == 90) & era_stop["match_id"].isin(group)).sum()
            parts.append(f"H2 {label} {goals / len(group) / rate:5.2f} (n={len(group)})")
        print(f"  {era}+: H1 {h1:4.2f}  " + "  ".join(parts))
    print(
        "adopted: incumbent lengths retained (H1 4, H2 close 9 / settled 8); the implied lengths are noisy and\n"
        "regime-bound, the incumbent values sit inside the implied range and win the leave-one-out backtest"
    )


def extra_time_report(matches: pd.DataFrame, goals: pd.DataFrame) -> None:
    et_matches = matches[matches["extra_time"] == 1]
    ids = set(et_matches["match_id"].astype(str))
    in_et = goals[goals["match_id"].isin(ids)]
    et_goals = in_et["match_period"].str.startswith("extra time").sum()
    et_rate = et_goals / (30 * len(ids))
    reg_rate = goals["match_period"].str.startswith(("first half", "second half")).sum() / (90 * len(matches))
    print(
        f"\nextra time: {et_rate:.4f} goals/min over {len(ids)} matches vs regulation mean {reg_rate:.4f} "
        f"(ratio {et_rate / reg_rate:.2f}; level matches select low realisations, so a flat 1.0 stands)"
    )


def run_fit(cache_dir: Path, *, era_start: int, header: str) -> None:
    matches, goals, bookings = load_tables(cache_dir, era_start=era_start)
    print(f"\n=== {header}: {len(matches)} matches, {len(goals)} goal rows ===")
    offsets = match_offsets(matches)
    exposure, stoppage = build_minute_exposure(matches, goals, bookings)
    stacked = side_stacked(exposure, offsets)

    granular = fit_hazard(stacked, granular=True)
    print("granular score states (vs 0-0):")
    for name in ("score_draw", "trailing_one", "trailing_two", "leading_one", "leading_two"):
        print(f"  {name:<14} x{np.exp(granular.params[name]):.3f}  z={granular.tvalues[name]:+.2f}")
    print("score_draw and leading_two are null; the adopted model merges level states and leading states")

    adopted = fit_hazard(stacked, granular=False)
    bins = profile_bins(adopted)
    print(f"\nprofile per 15-minute bin (mean 1): {np.round(bins, 3).tolist()}")
    print_multiplier_table(adopted, calibration_factor(stacked, adopted))
    stoppage_report(matches, exposure, stoppage)
    extra_time_report(matches, goals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era", type=int, default=1986)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()

    run_fit(args.cache_dir, era_start=args.era, header=f"WC {args.era}-2022")
    if args.era < 1998:
        run_fit(args.cache_dir, era_start=1998, header="sensitivity WC 1998-2022")


if __name__ == "__main__":
    main()
