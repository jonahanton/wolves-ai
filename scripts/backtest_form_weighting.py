"""Leak-free backtest of recent-form weighting in the base Poisson fit.

For each (form_half_life_days, form_weight) setting the model is refit once per
frozen holdout fold and scored on that fold's matches. RPS and log-loss are
compared against the single-decay baseline (form off) and the market consensus,
so a setting only earns a flip if it beats the baseline without trailing the
market by more than it already does.

Usage: uv run --project engine python scripts/backtest_form_weighting.py [--storage local]
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date

import duckdb
import numpy as np

from wolves.config import Settings
from wolves.data.store import DatasetStore
from wolves.data.tournaments import CLOSES_TOURNAMENTS
from wolves.gate.scoring import log_loss, rank_probability_score
from wolves.markets.devig import consensus_probabilities, power_devig
from wolves.models.contracts import DatasetHandle, Fixture, UnknownModelTeamError
from wolves.models.poisson import PoissonDecayModel
from wolves.observability.logging import configure_cli_logging
from wolves.s3.cli import add_storage_argument, apply_storage_choice

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HoldoutMatch:
    fit_as_of: date
    home_team: str
    away_team: str
    neutral: bool
    outcome: int
    market: np.ndarray


def _outcome(home_goals: int, away_goals: int, *, went_to_shootout: bool) -> int:
    if went_to_shootout or home_goals == away_goals:
        return 1
    return 0 if home_goals > away_goals else 2


def _consensus(trios: list[tuple[float, float, float]]) -> np.ndarray:
    per_book = []
    for home, draw, away in trios:
        devigged = power_devig([home, draw, away])
        per_book.append({"home": devigged[0], "draw": devigged[1], "away": devigged[2]})
    consensus = consensus_probabilities(per_book)
    return np.array([consensus["home"], consensus["draw"], consensus["away"]])


def load_closes_holdout(dataset: DatasetHandle) -> list[HoldoutMatch]:
    """The market-closes folds only (Euro 2020 onward), joined by team pair and
    nearest date. Skips the older workbook folds, whose odds column trips a
    date/timestamp mismatch in the shared loader on this dataset."""
    connection = duckdb.connect(str(dataset.path), read_only=True)
    try:
        close_rows = connection.execute(
            "select tournament, home_team, away_team, cast(commence_at as date),"
            " list(row(home_price, draw_price, away_price))"
            " from market_closes group by 1, 2, 3, 4"
        ).fetchall()
        results_by_slug = {
            t.slug: connection.execute(
                "select date, home_team, away_team, home_goals, away_goals, neutral from matches"
                " where tournament = ? and date between ? and ?",
                [t.results_tournament, t.first_match.isoformat(), t.last_match.isoformat()],
            ).fetchall()
            for t in CLOSES_TOURNAMENTS
        }
        shootouts = {
            (played, frozenset((home, away)))
            for played, home, away in connection.execute("select date, home_team, away_team from shootouts").fetchall()
        }
    finally:
        connection.close()

    closes: dict[tuple[str, frozenset[str]], list[tuple[date, str, list]]] = {}
    for tournament_slug, home, away, commence, trios in close_rows:
        closes.setdefault((tournament_slug, frozenset((home, away))), []).append((commence, home, list(trios)))

    matches: list[HoldoutMatch] = []
    for tournament in CLOSES_TOURNAMENTS:
        for played, home, away, home_goals, away_goals, neutral in results_by_slug[tournament.slug]:
            entries = closes.get((tournament.slug, frozenset((home, away))))
            if not entries:
                continue
            commence, listed_home, trios = min(entries, key=lambda e: abs((e[0] - played).days))
            if abs((commence - played).days) > 1:
                continue
            oriented = trios if listed_home == home else [(a, d, h) for h, d, a in trios]
            went_to_shootout = (played, frozenset((home, away))) in shootouts
            matches.append(
                HoldoutMatch(
                    fit_as_of=tournament.fit_as_of,
                    home_team=home,
                    away_team=away,
                    neutral=bool(neutral),
                    outcome=_outcome(home_goals, away_goals, went_to_shootout=went_to_shootout),
                    market=_consensus(oriented),
                )
            )
    return sorted(matches, key=lambda m: (m.fit_as_of, m.home_team))

# (form_half_life_days, form_weight). (0, 0) is the single-decay baseline.
GRID: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (180.0, 0.25),
    (180.0, 0.5),
    (365.0, 0.25),
    (365.0, 0.5),
    (365.0, 0.75),
    (180.0, 0.75),
)


@dataclass(frozen=True)
class Scored:
    model: np.ndarray
    market: np.ndarray
    outcomes: np.ndarray


def score_setting(
    dataset: DatasetHandle,
    holdout: list[HoldoutMatch],
    *,
    half_life_days: float | None,
    form_half_life: float,
    form_weight: float,
) -> Scored:
    model = PoissonDecayModel(
        **({"half_life_days": half_life_days} if half_life_days else {}),
        form_half_life_days=form_half_life,
        form_weight=form_weight,
    )
    states: dict[object, object] = {}
    model_probs, market_probs, outcomes = [], [], []
    for match in holdout:
        if match.fit_as_of not in states:
            states[match.fit_as_of] = model.fit(dataset, as_of=match.fit_as_of)
        try:
            fixture = Fixture(home=match.home_team, away=match.away_team, neutral=match.neutral)
            distribution = model.score_distribution(fixture, states[match.fit_as_of])
        except UnknownModelTeamError:
            continue
        model_probs.append(distribution.outcome_probs())
        market_probs.append(match.market)
        outcomes.append(match.outcome)
    return Scored(np.array(model_probs), np.array(market_probs), np.array(outcomes))


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Backtest recent-form weighting against the holdout and market")
    add_storage_argument(parser)
    args = parser.parse_args()
    settings = apply_storage_choice(Settings(), args.storage)

    path, manifest = DatasetStore(settings).fetch()
    dataset = DatasetHandle(path=path, dataset_id=manifest.dataset_id)
    half_life = PoissonDecayModel().half_life_days
    holdout = load_closes_holdout(dataset)
    logger.info("scoring %d holdout matches across %d settings", len(holdout), len(GRID))

    baseline = score_setting(dataset, holdout, half_life_days=half_life, form_half_life=0.0, form_weight=0.0)
    market_rps = rank_probability_score(baseline.market, baseline.outcomes)
    market_ll = log_loss(baseline.market, baseline.outcomes)
    base_rps = rank_probability_score(baseline.model, baseline.outcomes)
    base_ll = log_loss(baseline.model, baseline.outcomes)

    print(f"\nholdout: {baseline.outcomes.shape[0]} scored matches")
    print(f"market : RPS {market_rps:.5f}  logloss {market_ll:.5f}")
    print(f"\n{'form_hl':>8}{'weight':>8}{'RPS':>10}{'dRPS':>9}{'logloss':>10}{'dLL':>9}  verdict")
    print(f"{'(off)':>8}{'-':>8}{base_rps:>10.5f}{0.0:>+9.5f}{base_ll:>10.5f}{0.0:>+9.5f}  baseline")

    for form_hl, weight in GRID:
        if (form_hl, weight) == (0.0, 0.0):
            continue
        scored = score_setting(dataset, holdout, half_life_days=half_life, form_half_life=form_hl, form_weight=weight)
        rps = rank_probability_score(scored.model, scored.outcomes)
        ll = log_loss(scored.model, scored.outcomes)
        d_rps, d_ll = rps - base_rps, ll - base_ll
        verdict = "better" if d_rps < 0 and d_ll < 0 else ("mixed" if d_rps < 0 or d_ll < 0 else "worse")
        print(f"{form_hl:>8.0f}{weight:>8.2f}{rps:>10.5f}{d_rps:>+9.5f}{ll:>10.5f}{d_ll:>+9.5f}  {verdict}")

    print("\nFlip the default only on a setting that is 'better' (both scores improve) and holds up out of sample.")


if __name__ == "__main__":
    main()
