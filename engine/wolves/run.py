"""One-shot sim entrypoint, run daily by the production scheduler. The
date-derived run id makes reruns for the same day replace, not duplicate."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, date, datetime

from wolves import ENGINE_VERSION
from wolves.config import Settings
from wolves.sim.api import run_simulation
from wolves.snapshot import RunMeta, Snapshot
from wolves.store.publish import SnapshotPublisher

logger = logging.getLogger(__name__)


def run_id_for(as_of: date) -> str:
    return f"run-{as_of:%Y%m%d}"


def generate_snapshot(settings: Settings, *, n_sims: int, seed: int = 0, run_id: str | None = None) -> Snapshot:
    """Run the simulation and assemble a snapshot."""
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the daily forecast")
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    daily_run(settings, as_of=args.as_of, n_sims=args.sims, seed=args.seed)


if __name__ == "__main__":
    main()
