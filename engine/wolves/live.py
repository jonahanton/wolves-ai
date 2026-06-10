"""Match-day live update: poll results, overlay them on the sim with the
latest agent rating overrides, and publish a fresh snapshot. One pass per
invocation because the scheduler owns the cadence; --loop exists for local
dev only. A pass with no results beyond the latest snapshot is a no-op."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from wolves import ENGINE_VERSION
from wolves.clients.api_football import ApiFootballClient, FakeFixturesClient, FixturesClient
from wolves.config import Settings
from wolves.sim.api import run_simulation
from wolves.sim.format import PlayedResult, load_format, load_results
from wolves.sim.overlay import results_from_fixtures
from wolves.snapshot import RunMeta, Snapshot
from wolves.store.publish import SnapshotPublisher

logger = logging.getLogger(__name__)


def latest_snapshot(snapshot_dir: Path) -> Snapshot | None:
    """Return the newest readable snapshot, ignoring the latest.json pointer."""
    newest: Snapshot | None = None
    if not snapshot_dir.exists():
        return None
    for path in snapshot_dir.glob("*.json"):
        if path.name == "latest.json":
            continue
        try:
            snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            logger.warning("skipping unreadable snapshot %s", path)
            continue
        if newest is None or snapshot.run.created_at > newest.run.created_at:
            newest = snapshot
    return newest


def latest_agent_overrides(snapshot_dir: Path) -> dict[str, float]:
    """Rating overrides from the newest snapshot that carries an agent block."""
    newest: Snapshot | None = None
    if not snapshot_dir.exists():
        return {}
    for path in snapshot_dir.glob("*.json"):
        if path.name == "latest.json":
            continue
        try:
            snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            continue
        if snapshot.agent is None:
            continue
        if newest is None or snapshot.run.created_at > newest.run.created_at:
            newest = snapshot
    if newest is None or newest.agent is None:
        return {}
    return {o.team_id: o.delta_elo for o in newest.agent.rating_overrides}


def pending_results(
    overlay: dict[int, PlayedResult],
    *,
    file_results: dict[int, PlayedResult],
    previous: Snapshot | None,
) -> dict[int, PlayedResult]:
    """Polled results not yet baked into the results file or the latest snapshot.

    A match absent from the previous snapshot's forecast list was already
    overlaid as played when that snapshot ran, so it is not new information."""
    fresh = {match: result for match, result in overlay.items() if match not in file_results}
    if previous is None:
        return fresh
    forecast = {entry.match for entry in previous.matches}
    return {match: result for match, result in fresh.items() if match in forecast}


async def live_pass(settings: Settings, *, fixtures: FixturesClient, n_sims: int, seed: int = 0) -> bool:
    """Run one deterministic update; return True when a snapshot was published."""
    publisher = SnapshotPublisher(settings)
    if not publisher.run_enabled():
        logger.info("run_enabled is off; skipping the live pass")
        return False

    fmt = load_format(settings.data_dir)
    overlay = results_from_fixtures(fmt, await fixtures.fixtures())
    pending = pending_results(
        overlay,
        file_results=load_results(settings.data_dir),
        previous=latest_snapshot(settings.snapshot_dir),
    )
    if not pending:
        logger.info("no new results; live pass is a no-op")
        return False

    overrides = latest_agent_overrides(settings.snapshot_dir)
    now = datetime.now(UTC)
    run_id = now.strftime("live-%Y%m%d-%H%M%S")
    created_at = now.isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        outputs = run_simulation(overrides, {}, n_sims, seed, extra_results=overlay)
    except Exception:
        publisher.record_failure(run_id=run_id, created_at=created_at, started=started)
        raise

    snapshot = Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=created_at,
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="live",
        ),
        england=outputs.england,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
    )
    s3_key = publisher.publish(snapshot, as_of=now.date(), started=started)
    logger.info(
        "live run %s applied %d new result(s) with %d override(s) (s3_key=%s)",
        run_id,
        len(pending),
        len(overrides),
        s3_key or "local",
    )
    return True


def build_fixtures_client(settings: Settings) -> FixturesClient:
    if settings.api_football_key:
        return ApiFootballClient(settings.api_football_key)
    return FakeFixturesClient()


async def _run(args: argparse.Namespace, settings: Settings) -> None:
    fixtures = build_fixtures_client(settings)
    try:
        while True:
            await live_pass(settings, fixtures=fixtures, n_sims=args.sims, seed=args.seed)
            if not args.loop:
                return
            await asyncio.sleep(args.interval)
    finally:
        await fixtures.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run a live results update pass")
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--loop", action="store_true", help="poll repeatedly; local dev only")
    parser.add_argument("--interval", type=float, default=900.0, help="seconds between --loop passes")
    args = parser.parse_args()
    asyncio.run(_run(args, settings))


if __name__ == "__main__":
    main()
