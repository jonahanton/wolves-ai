"""The market-implied base world: de-vigged consensus expressed as strengths,
so the seeded fallback mixture carries both bases even when every node fails."""

from __future__ import annotations

import logging
from pathlib import Path

from wolves.forecast import Forecaster, StrengthPerturbation
from wolves.markets.series import load_series
from wolves.sim.api import UnknownTeamError

logger = logging.getLogger(__name__)

_TOP_N = 8
_GAP_FLOOR_PP = 1.0
_BISECT_ITERATIONS = 10
_SEED_SIMS = 10_000


def latest_market(archive_dir: Path) -> dict[str, float]:
    series = load_series(archive_dir)
    latest = next((p for p in reversed(series) if p.outright_bookmakers), None)
    return latest.outright_bookmakers if latest else {}


def _implied_delta(forecaster: Forecaster, team: str, target: float, *, seed: int) -> float:
    lo, hi = -0.5, 0.5
    for _ in range(_BISECT_ITERATIONS):
        mid = (lo + hi) / 2
        pert = StrengthPerturbation(team=team, delta=mid, reason="market inversion probe")
        p = forecaster.title_probs(n_sims=_SEED_SIMS, seed=seed, perturbations=(pert,)).get(team, 0.0)
        if p < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def market_base_perturbations(
    forecaster: Forecaster, market: dict[str, float], *, seed: int = 0
) -> list[StrengthPerturbation]:
    """One strength delta per top contender whose price materially disagrees
    with the model; per-team inversions compose into an approximate joint world."""
    base = forecaster.title_probs(n_sims=_SEED_SIMS, seed=seed)
    perturbations: list[StrengthPerturbation] = []
    for team, target in sorted(market.items(), key=lambda kv: -kv[1])[:_TOP_N]:
        model_p = base.get(team)
        if model_p is None or abs(model_p - target) * 100 < _GAP_FLOOR_PP:
            continue
        delta = round(_implied_delta(forecaster, team, target, seed=seed), 4)
        if abs(delta) >= 0.45:
            # The bisection hit its boundary: the price is outside what any
            # plausible strength shift reproduces.
            logger.warning("market inversion for %s hit the boundary (%.2f); skipping", team, delta)
            continue
        perturbations.append(
            StrengthPerturbation(
                team=team,
                delta=delta,
                reason=f"market-implied: de-vigged {target * 100:.1f}% vs model {model_p * 100:.1f}%",
            )
        )
    return perturbations


def seed_baseline_payload(forecaster: Forecaster | None, archive_dir: Path) -> tuple[dict, str]:
    """The fallback mixture payload and its summary: two bases at the fitted
    blend weight when the market is priceable, the bare model world otherwise.
    The mixture key is always populated so the validator's escalation and
    market anchors bite on the fallback too."""
    single = {"weights": {"baseline": 1.0}, "worlds": {"baseline": {"perturbations": []}}, "mixture": {}}
    single_summary = "Baseline single-world mixture: the unperturbed champion simulation, the quiet-day fallback."
    if forecaster is None:
        return single, single_summary
    base = forecaster.title_probs(n_sims=_SEED_SIMS, seed=0)
    single["mixture"] = {team: round(p, 6) for team, p in base.items()}
    market = latest_market(archive_dir)
    if not market:
        return single, single_summary
    try:
        perturbations = market_base_perturbations(forecaster, market)
    except (UnknownTeamError, ValueError) as exc:
        logger.warning("market base inversion failed (%s); seeding the single-world baseline", exc)
        return single, single_summary
    # An unfitted blend weight would hand the fallback wholly to one base.
    model_weight = forecaster.champion.blend_weight or 0.27
    market_world = forecaster.title_probs(n_sims=_SEED_SIMS, seed=0, perturbations=tuple(perturbations))
    mixture = {
        team: round(model_weight * p + (1.0 - model_weight) * market_world.get(team, p), 6) for team, p in base.items()
    }
    payload = {
        "weights": {"model_base": round(model_weight, 4), "market_base": round(1.0 - model_weight, 4)},
        "worlds": {
            "model_base": {"perturbations": []},
            "market_base": {"perturbations": [p.model_dump(mode="json") for p in perturbations]},
        },
        "mixture": mixture,
    }
    summary = (
        f"Two-base fallback mixture: champion simulation ({model_weight:.2f}) and the market-implied world "
        f"({1.0 - model_weight:.2f}, {len(perturbations)} inverted contender(s)), the quiet-day fallback."
    )
    return payload, summary
