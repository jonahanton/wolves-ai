"""Match-day live pass: overlay polled results plus the published agent worlds, republish."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from wolves import ENGINE_VERSION
from wolves.agent.forecast_artifact import PublishedWorld, mixed_outputs, worlds_from_payload
from wolves.clients.api_football import ApiFootballClient, FakeFixturesClient, FixturesClient
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.layout import SNAPSHOT
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.format import PlayedResult, load_format, load_results
from wolves.sim.overlay import results_from_fixtures
from wolves.snapshot import RunMeta, Snapshot

logger = logging.getLogger(__name__)


def scan_snapshots(snapshot_dir: Path) -> tuple[Snapshot | None, list[PublishedWorld]]:
    """One directory scan: the newest readable snapshot, plus the published
    world configurations from the newest snapshot with an agent block."""
    newest: Snapshot | None = None
    newest_agent: Snapshot | None = None
    if not snapshot_dir.exists():
        return None, []
    for path in snapshot_dir.rglob("*.json"):
        if path.name == "latest.json":
            continue
        try:
            snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            logger.warning("skipping unreadable snapshot %s", path)
            continue
        if newest is None or snapshot.run.created_at > newest.run.created_at:
            newest = snapshot
        if snapshot.agent is not None and (
            newest_agent is None or snapshot.run.created_at > newest_agent.run.created_at
        ):
            newest_agent = snapshot
    worlds: list[PublishedWorld] = []
    if newest_agent is not None and newest_agent.agent is not None and newest_agent.agent.worlds:
        payload = {
            "weights": {w.name: w.weight for w in newest_agent.agent.worlds},
            "worlds": {w.name: {"perturbations": w.perturbations} for w in newest_agent.agent.worlds},
        }
        worlds = worlds_from_payload(payload)
    return newest, worlds


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


async def live_pass(
    settings: Settings,
    *,
    fixtures: FixturesClient,
    n_sims: int,
    seed: int = 0,
    forecaster: Forecaster | None = None,
) -> bool:
    """Run one deterministic update; return True when a snapshot was published."""
    publisher = SnapshotPublisher(settings)
    if not publisher.run_enabled():
        logger.info("run_enabled is off; skipping the live pass")
        return False

    fmt = load_format(settings.data_dir)
    overlay = results_from_fixtures(fmt, await fixtures.fixtures())
    # Fresh containers hold no snapshots; without this the continuity check
    # and the agent overrides silently degrade to nothing.
    ArtifactStore(settings).sync_down(prefix=SNAPSHOT.prefix)
    previous, worlds = scan_snapshots(settings.runs_root / "snapshots")
    pending = pending_results(
        overlay,
        file_results=load_results(settings.data_dir),
        previous=previous,
    )
    if not pending:
        logger.info("no new results; live pass is a no-op")
        return False
    now = datetime.now(UTC)
    run_id = now.strftime("live-%Y%m%d-%H%M%S")
    created_at = now.isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        if forecaster is None:
            forecaster = Forecaster(settings)
            forecaster.fit()
        outputs = mixed_outputs(
            forecaster,
            worlds or [PublishedWorld(name="baseline", weight=1.0)],
            n_sims=n_sims,
            seed=seed,
            extra_results=overlay,
        )
    except Exception:
        publisher.record_failure(run_id=run_id, created_at=created_at, started=started)
        raise

    snapshot = Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=created_at,
            as_of=now.date().isoformat(),
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="live",
        ),
        focus=outputs.focus,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
    )
    s3_key = publisher.publish(snapshot, as_of=now.date(), started=started)
    logger.info(
        "live run %s applied %d new result(s) across %d world(s) (s3_key=%s)",
        run_id,
        len(pending),
        len(worlds) or 1,
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
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run a live results update pass")
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--loop", action="store_true", help="poll repeatedly; local dev only")
    parser.add_argument("--interval", type=float, default=900.0, help="seconds between --loop passes")
    add_storage_argument(parser)
    args = parser.parse_args()
    asyncio.run(_run(args, apply_storage_choice(settings, args.storage)))


if __name__ == "__main__":
    main()
