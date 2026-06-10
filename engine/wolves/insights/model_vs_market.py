"""The daily question in one table: where does the model disagree with the
market, by how much, and what do we publish."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wolves.forecast import Forecaster
from wolves.markets.blend import blend_probabilities
from wolves.markets.series import load_series

TOP_GAPS = 20


class TeamComparison(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    team: str
    model_p_title: float
    market_p_title: float | None
    polymarket_p_title: float | None
    blend_p_title: float | None
    gap_pp: float


class ModelVsMarket(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    as_of: str
    model_weight: float
    comparisons: list[TeamComparison]


def model_vs_market(forecaster: Forecaster, archive_dir: Path, *, n_sims: int = 50_000, seed: int = 0) -> ModelVsMarket:
    model = forecaster.title_probs(n_sims=n_sims, seed=seed)
    series = load_series(archive_dir)
    latest = series[-1] if series else None
    market = latest.outright_bookmakers if latest else {}
    polymarket = latest.outright_polymarket if latest else {}
    weight = forecaster.champion.blend_weight
    blend = blend_probabilities(model, market, model_weight=weight) if market else {}

    comparisons = [
        TeamComparison(
            team=team,
            model_p_title=round(p_model, 4),
            market_p_title=market.get(team),
            polymarket_p_title=polymarket.get(team),
            blend_p_title=round(blend[team], 4) if team in blend else None,
            gap_pp=round((p_model - market[team]) * 100.0, 2) if team in market else 0.0,
        )
        for team, p_model in model.items()
    ]
    comparisons.sort(key=lambda c: -abs(c.gap_pp))
    return ModelVsMarket(
        as_of=latest.captured_at if latest else "no market snapshots held",
        model_weight=weight,
        comparisons=comparisons[:TOP_GAPS],
    )
