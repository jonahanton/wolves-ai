"""Daily sim entrypoint; the date-derived run id makes reruns replace, not duplicate."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, date, datetime

from pydantic import BaseModel

from wolves import ENGINE_VERSION
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.gate.registry import ELO_CHAMPION_ID
from wolves.markets.blend import blend_probabilities
from wolves.markets.outright import build_clients, outright_consensus
from wolves.observability.logging import configure_cli_logging
from wolves.publish_distributions import build_run_distributions
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.fitted import FittedStateStore
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.api import run_simulation
from wolves.sim.results_store import persisted_results, played_match_records
from wolves.snapshot import ChampionBlock, MarketsBlock, RunMeta, Snapshot

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

    # Market sources must never kill the daily run; the block is simply omitted.
    try:
        market = asyncio.run(fetch())
    except Exception:
        logger.warning("markets fetch failed; omitting the markets block", exc_info=True)
        return None
    if not market:
        return None
    weight = forecaster.champion.blend_weight
    return MarketsBlock(
        model_probs={k: round(v, 4) for k, v in model_probs.items()},
        market_probs={k: round(v, 4) for k, v in market.items()},
        blend_probs={k: round(v, 4) for k, v in blend_probabilities(model_probs, market, model_weight=weight).items()},
        model_weight=weight,
    )


def generate_snapshot(
    settings: Settings, *, n_sims: int, seed: int = 0, run_id: str | None = None
) -> tuple[Snapshot, dict[str, BaseModel]]:
    """Run the trusted model's simulation (or the Elo baseline) and assemble a
    snapshot plus its sidecar payloads."""
    forecaster = Forecaster(settings)
    # Read through this run's settings so a per-run --storage choice governs
    # which persisted results the published snapshot sees.
    played = persisted_results(settings)
    model_path = forecaster.champion.model_id != ELO_CHAMPION_ID
    champion = None
    markets = None
    distributions = None
    sidecars: dict[str, BaseModel] = {}
    played_records = played_match_records(settings)
    if model_path:
        forecaster.fit(extra_results=played_records)
        if run_id:
            FittedStateStore(ArtifactStore(settings)).publish(forecaster.state, run_id=run_id)
        result = forecaster.simulate(n_sims=n_sims, seed=seed, results=forecaster.played_results(extra_results=played))
        outputs = forecaster.sim_outputs(n_sims=n_sims, seed=seed, extra_results=played, result=result)
        champion = ChampionBlock(
            id=forecaster.champion.model_id,
            version=forecaster.champion.model_version,
            dataset_id=forecaster.champion.dataset_id,
            half_life_days=forecaster.champion.half_life_days,
            blend_weight=forecaster.champion.blend_weight,
            results_overlaid=len(played_records),
        )
        distributions, sidecars = build_run_distributions(
            forecaster.fmt,
            {"baseline": result},
            {"baseline": 1.0},
            settings=settings,
            played=frozenset(forecaster.played_results(extra_results=played)),
            rng_seed=seed,
        )
        model_probs = {t.team_id: t.champion_prob for t in outputs.teams}
        markets = _markets_block(settings, forecaster, model_probs)
    else:
        outputs = run_simulation({}, {}, n_sims, seed, extra_results=played)

    now = datetime.now(UTC)
    snapshot = Snapshot(
        run=RunMeta(
            run_id=run_id or now.strftime("run-%Y%m%d-%H%M%S"),
            created_at=now.isoformat(timespec="seconds"),
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="sim_only",
        ),
        focus=outputs.focus,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
        champion=champion,
        markets=markets,
        distributions=distributions,
    )
    return snapshot, sidecars


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
        snapshot, sidecars = generate_snapshot(settings, n_sims=n_sims, seed=seed, run_id=run_id)
    except Exception:
        publisher.record_failure(run_id=run_id, created_at=created_at, started=started)
        raise

    s3_key = publisher.publish(snapshot, as_of=as_of, started=started, sidecars=sidecars)
    logger.info("daily run %s completed in %.1fs (s3_key=%s)", run_id, time.monotonic() - started, s3_key or "local")
    return True


def main() -> None:
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the daily forecast")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    add_storage_argument(parser)
    args = parser.parse_args()
    daily_run(apply_storage_choice(settings, args.storage), as_of=args.as_of, n_sims=args.sims, seed=args.seed)


if __name__ == "__main__":
    main()
