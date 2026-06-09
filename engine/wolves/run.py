from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime

from wolves.config import Settings
from wolves.sim.api import run_simulation
from wolves.snapshot import RunMeta, Snapshot

logger = logging.getLogger(__name__)

ENGINE_VERSION = "0.2.0"


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
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    parser = argparse.ArgumentParser(description="Generate a forecast snapshot")
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    snapshot = generate_snapshot(settings, n_sims=args.sims, seed=args.seed)
    payload = snapshot.model_dump_json(indent=1)

    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    (settings.snapshot_dir / f"{snapshot.run.run_id}.json").write_text(payload)
    (settings.snapshot_dir / "latest.json").write_text(payload)

    win_path = next(p for p in snapshot.england.paths if p.finish == "win_group")
    top = win_path.opponents[0] if win_path.opponents else None
    logger.info("snapshot %s written to %s", snapshot.run.run_id, settings.snapshot_dir)
    logger.info(
        "England win Group L %.0f%%; most likely R32 opponent if so: %s (%.0f%%) in %s",
        snapshot.england.finish_probs["win_group"] * 100,
        top.team_id if top else "n/a",
        (top.prob if top else 0) * 100,
        win_path.city,
    )
    logger.info("reach probabilities: %s", json.dumps(snapshot.england.reach_probs))


if __name__ == "__main__":
    main()
