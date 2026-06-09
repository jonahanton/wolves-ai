"""Daily entrypoint for the scheduled Fargate task. Defence in depth on the
kill switch: the EventBridge schedule state is the primary switch, the
run_enabled control item is checked here so an in-flight schedule change still
stops the run. An unreachable table must not block local dev, so it downgrades
to a warning and the run proceeds."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, date, datetime

from wolves.config import Settings
from wolves.run import generate_snapshot
from wolves.store.records import RunRecord, RunStatus
from wolves.store.store import RunIndex, RunIndexUnavailableError, SnapshotStore

logger = logging.getLogger(__name__)


def run_id_for(as_of: date) -> str:
    """Derive the deterministic run id that makes reruns replace, not duplicate."""
    return f"run-{as_of:%Y%m%d}"


def build_run_index(settings: Settings) -> RunIndex | None:
    """Construct the run index when DynamoDB config is present."""
    if not settings.dynamo_endpoint and not settings.snapshot_bucket:
        return None
    return RunIndex(
        table_name=settings.dynamo_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamo_endpoint or None,
    )


def daily_run(settings: Settings, *, as_of: date, n_sims: int, seed: int = 0) -> bool:
    """Run the daily forecast unless disabled; return True when a run happened."""
    index = build_run_index(settings)
    if index is not None and not _run_enabled(index):
        logger.info("run_enabled is off; skipping the daily run for %s", as_of)
        return False

    run_id = run_id_for(as_of)
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        snapshot = generate_snapshot(settings, n_sims=n_sims, seed=seed, run_id=run_id)
    except Exception:
        _record(index, run_id=run_id, created_at=created_at, s3_key="", status="failed", started=started, kind="")
        raise

    payload = snapshot.model_dump_json(indent=1)
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    (settings.snapshot_dir / f"{run_id}.json").write_text(payload)
    (settings.snapshot_dir / "latest.json").write_text(payload)

    s3_key = ""
    if settings.snapshot_bucket:
        store = SnapshotStore(bucket=settings.snapshot_bucket, region=settings.aws_region)
        s3_key = store.put_snapshot(snapshot, as_of=as_of)

    _record(
        index,
        run_id=run_id,
        created_at=created_at,
        s3_key=s3_key,
        status="completed",
        started=started,
        kind=snapshot.run.kind,
    )
    logger.info("daily run %s completed in %.1fs (s3_key=%s)", run_id, time.monotonic() - started, s3_key or "local")
    return True


def _run_enabled(index: RunIndex) -> bool:
    try:
        return index.run_enabled()
    except RunIndexUnavailableError:
        logger.warning("run index unreachable; proceeding as enabled")
        return True


def _record(
    index: RunIndex | None,
    *,
    run_id: str,
    created_at: str,
    s3_key: str,
    status: RunStatus,
    started: float,
    kind: str,
) -> None:
    if index is None:
        return
    record = RunRecord(
        run_id=run_id,
        created_at=created_at,
        s3_key=s3_key,
        status=status,
        cost=0.0,
        duration_s=round(time.monotonic() - started, 3),
        kind=kind or "sim_only",
    )
    try:
        index.record_run(record)
    except RunIndexUnavailableError:
        logger.warning("run index unreachable; %s not indexed", run_id)


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
