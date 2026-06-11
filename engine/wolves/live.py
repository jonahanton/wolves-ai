"""Match-day live pass: overlay polled results plus the published agent worlds, republish."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from wolves import ENGINE_VERSION
from wolves.agent.forecast_artifact import PublishedWorld, mixed_outputs, worlds_from_payload
from wolves.clients.api_football import (
    ApiFootballClient,
    ApiFootballPayloadError,
    FakeFixturesClient,
    FixturesClient,
)
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.live_state import LiveStateStore, build_live_state
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.layout import SNAPSHOT
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.format import PlayedResult, load_format, load_results
from wolves.sim.overlay import results_from_fixtures
from wolves.sim.results_store import ResultsStore, played_match_records
from wolves.snapshot import RunMeta, Snapshot

logger = logging.getLogger(__name__)


def scan_snapshots(snapshot_dir: Path) -> tuple[Snapshot | None, list[PublishedWorld]]:
    """Find the newest snapshot and latest published agent worlds."""
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


def publishable_results(
    overlay: dict[int, PlayedResult],
    *,
    file_results: dict[int, PlayedResult],
    previous: Snapshot | None,
) -> dict[int, PlayedResult]:
    """Select polled results that still need a live snapshot publish."""
    if previous is None:
        return {match: result for match, result in overlay.items() if file_results.get(match) != result}
    forecast = {entry.match for entry in previous.matches}
    return {
        match: result
        for match, result in overlay.items()
        if match in forecast or file_results.get(match) != result
    }


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
    artifacts = ArtifactStore(settings)
    live_states = LiveStateStore(artifacts)
    try:
        polled = await fixtures.fixtures()
    except (httpx.HTTPError, ApiFootballPayloadError) as exc:
        live_states.record_failure(message=str(exc))
        logger.warning("live poll failed; keeping the previous live state: %s", exc)
        return False
    fetched_at = datetime.now(UTC)
    overlay = results_from_fixtures(fmt, polled)
    store = ResultsStore(artifacts)
    known = store.load()
    # Fresh containers hold no snapshots; without this the continuity check
    # and the agent overrides silently degrade to nothing.
    artifacts.sync_down(prefix=SNAPSHOT.prefix)
    previous, worlds = scan_snapshots(settings.runs_root / "snapshots")
    pending = publishable_results(
        overlay,
        file_results=load_results(settings.data_dir) | known.results,
        previous=previous,
    )
    # Persist before simulating: daily and agent runs read the store, so a
    # polled result must survive even when this pass publishes nothing.
    finished = [f for f in polled if f.status == "finished"]
    merged = store.record(overlay, fixtures=finished)
    if forecaster is None:
        forecaster = Forecaster(settings)
    if not forecaster.is_fitted:
        forecaster.fit(extra_results=played_match_records(settings))
    live_states.put(
        build_live_state(
            forecaster,
            polled,
            fetched_at=fetched_at,
            results=merged.results,
            previous=previous,
            n_sims=n_sims,
            seed=seed,
            stale_after_s=settings.live_stale_after_s,
        )
    )
    if not pending:
        logger.info("no new or corrected results; live snapshot publish is a no-op")
        return False
    now = datetime.now(UTC)
    run_id = now.strftime("live-%Y%m%d-%H%M%S")
    created_at = now.isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        outputs = mixed_outputs(
            forecaster,
            worlds or [PublishedWorld(name="baseline", weight=1.0)],
            n_sims=n_sims,
            seed=seed,
            extra_results=merged.results,
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
    if settings.storage_mode != "local":
        raise RuntimeError("API_FOOTBALL_KEY is required for cloud-backed live polling")
    return FakeFixturesClient()


async def _run(args: argparse.Namespace, settings: Settings) -> None:
    fixtures = build_fixtures_client(settings)
    forecaster = Forecaster(settings)
    try:
        while True:
            try:
                published = await live_pass(
                    settings, fixtures=fixtures, n_sims=args.sims, seed=args.seed, forecaster=forecaster
                )
            except Exception:
                if not args.loop:
                    raise
                # One bad pass must not end the match-day task.
                logger.exception("live pass failed; continuing the loop")
                published = False
            if not args.loop:
                return
            if published:
                # A publish means a result landed; refit next pass or the loop's ratings drift.
                forecaster = Forecaster(settings)
            await asyncio.sleep(args.interval)
    finally:
        await fixtures.aclose()


def main() -> None:
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run a live results update pass")
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--loop", action="store_true", help="poll repeatedly for the match-day task")
    parser.add_argument(
        "--interval", type=float, default=settings.live_poll_interval_s, help="seconds between --loop passes"
    )
    add_storage_argument(parser)
    args = parser.parse_args()
    asyncio.run(_run(args, apply_storage_choice(settings, args.storage)))


if __name__ == "__main__":
    main()
