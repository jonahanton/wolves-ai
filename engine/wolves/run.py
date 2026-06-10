"""One-shot sim entrypoint, run daily by the production scheduler. The
date-derived run id makes reruns for the same day replace, not duplicate."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, date, datetime

from wolves import ENGINE_VERSION
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.gate.registry import ELO_CHAMPION_ID
from wolves.markets.blend import blend_probabilities
from wolves.markets.outright import build_clients, outright_consensus
from wolves.observability.logging import configure_cli_logging
from wolves.sim.api import run_simulation
from wolves.snapshot import ChampionBlock, MarketsBlock, RunMeta, Snapshot, TeamInterval
from wolves.store.publish import SnapshotPublisher

logger = logging.getLogger(__name__)


def run_id_for(as_of: date) -> str:
    return f"run-{as_of:%Y%m%d}"


def _markets_block(settings: Settings, forecaster: Forecaster, model_probs: dict[str, float]) -> MarketsBlock | None:
    async def fetch() -> dict[str, float]:
        odds, polymarket = build_clients(settings)
        try:
            return await outright_consensus(settings, forecaster.fmt, odds=odds, polymarket=polymarket)
        finally:
            await odds.aclose()
            await polymarket.aclose()

    market = asyncio.run(fetch())
    if not market:
        return None
    weight = forecaster.champion.blend_weight
    return MarketsBlock(
        model_probs={k: round(v, 4) for k, v in model_probs.items()},
        market_probs={k: round(v, 4) for k, v in market.items()},
        blend_probs={k: round(v, 4) for k, v in blend_probabilities(model_probs, market, model_weight=weight).items()},
        model_weight=weight,
    )


def generate_snapshot(settings: Settings, *, n_sims: int, seed: int = 0, run_id: str | None = None) -> Snapshot:
    """Run the trusted model's simulation (or the Elo baseline) and assemble a snapshot."""
    forecaster = Forecaster(settings)
    model_path = forecaster.champion.model_id != ELO_CHAMPION_ID
    champion = None
    intervals: list[TeamInterval] = []
    markets = None
    if model_path:
        forecaster.fit()
        outputs = forecaster.sim_outputs(n_sims=n_sims, seed=seed)
        champion = ChampionBlock(
            id=forecaster.champion.model_id,
            version=forecaster.champion.model_version,
            dataset_version=forecaster.champion.dataset_version,
            half_life_days=forecaster.champion.half_life_days,
            blend_weight=forecaster.champion.blend_weight,
        )
        intervals = [
            TeamInterval(team_id=team, lo=round(lo, 4), hi=round(hi, 4))
            for team, (lo, hi) in forecaster.intervals(seed=seed).items()
        ]
        model_probs = {t.team_id: t.champion_prob for t in outputs.teams}
        markets = _markets_block(settings, forecaster, model_probs)
    else:
        outputs = run_simulation({}, {}, n_sims, seed)

    now = datetime.now(UTC)
    return Snapshot(
        run=RunMeta(
            run_id=run_id or now.strftime("run-%Y%m%d-%H%M%S"),
            created_at=now.isoformat(timespec="seconds"),
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="sim_only",
        ),
        england=outputs.england,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
        champion=champion,
        intervals=intervals,
        markets=markets,
    )


def daily_run(settings: Settings, *, as_of: date, n_sims: int, seed: int = 0) -> bool:
    """Run the daily forecast unless disabled; return True when a run happened."""
    publisher = SnapshotPublisher(settings)
    if not publisher.run_enabled():
        logger.info("run_enabled is off; skipping the daily run for %s", as_of)
        return False

    run_id = run_id_for(as_of)
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        snapshot = generate_snapshot(settings, n_sims=n_sims, seed=seed, run_id=run_id)
    except Exception:
        publisher.record_failure(run_id=run_id, created_at=created_at, started=started)
        raise

    s3_key = publisher.publish(snapshot, as_of=as_of, started=started)
    logger.info("daily run %s completed in %.1fs (s3_key=%s)", run_id, time.monotonic() - started, s3_key or "local")
    return True


def main() -> None:
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the daily forecast")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    daily_run(settings, as_of=args.as_of, n_sims=args.sims, seed=args.seed)


if __name__ == "__main__":
    main()
