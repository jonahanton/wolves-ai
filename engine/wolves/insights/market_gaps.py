"""The daily question in one table: where does the model disagree with the
market, by how much, and what do we publish."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wolves.forecast import Forecaster
from wolves.markets.blend import blend_probabilities
from wolves.markets.series import load_series

TOP_GAPS = 20


class TeamGap(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    team: str
    model_p_title: float
    market_p_title: float | None
    polymarket_p_title: float | None
    blend_p_title: float | None
    gap_pp: float | None
    polymarket_gap_pp: float | None
    legs_disagree_pp: float | None


class MarketGaps(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    as_of: str
    model_weight: float
    gaps: list[TeamGap]
    prices_updated_oldest: str | None = None
    prices_updated_newest: str | None = None


def _pp(a: float, b: float | None) -> float | None:
    return round((a - b) * 100.0, 2) if b is not None else None


def market_gaps(forecaster: Forecaster, archive_dir: Path, *, n_sims: int = 50_000, seed: int = 0) -> MarketGaps:
    model = forecaster.title_probs(n_sims=n_sims, seed=seed)
    series = load_series(archive_dir)
    latest = series[-1] if series else None
    market = latest.outright_bookmakers if latest else {}
    polymarket = latest.outright_polymarket if latest else {}
    weight = forecaster.champion.blend_weight
    blend = blend_probabilities(model, market, model_weight=weight) if market else {}

    gaps = [
        TeamGap(
            team=team,
            model_p_title=round(p_model, 4),
            market_p_title=market.get(team),
            polymarket_p_title=polymarket.get(team),
            blend_p_title=round(blend[team], 4) if team in blend else None,
            gap_pp=_pp(p_model, market.get(team)),
            polymarket_gap_pp=_pp(p_model, polymarket.get(team)),
            legs_disagree_pp=_pp(market[team], polymarket.get(team)) if team in market else None,
        )
        for team, p_model in model.items()
    ]
    gaps.sort(key=lambda g: -max(abs(g.gap_pp or 0.0), abs(g.polymarket_gap_pp or 0.0)))
    return MarketGaps(
        as_of=latest.captured_at if latest else "no market snapshots held",
        model_weight=weight,
        gaps=gaps[:TOP_GAPS],
        prices_updated_oldest=latest.outright_updated_oldest if latest else None,
        prices_updated_newest=latest.outright_updated_newest if latest else None,
    )
