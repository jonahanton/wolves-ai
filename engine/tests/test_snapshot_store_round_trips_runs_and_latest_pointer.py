from __future__ import annotations

import json
from datetime import date

import boto3
import pytest
from moto import mock_aws

from wolves.config import Settings
from wolves.run import generate_snapshot
from wolves.store.init import ensure_table
from wolves.store.records import RunRecord
from wolves.store.store import RunIndex, SnapshotStore

REGION = "eu-west-2"
TABLE = "wolves-forecaster"
AS_OF = date(2026, 6, 17)


@pytest.fixture(scope="module")
def snapshot():
    return generate_snapshot(Settings(), n_sims=200, seed=7, run_id="run-20260617")


def _record(created_at: str, *, status: str = "completed") -> RunRecord:
    return RunRecord(
        run_id="run-20260617",
        created_at=created_at,
        s3_key="snapshots/2026/06/17/run-20260617.json",
        status="failed" if status == "failed" else "completed",
        cost=0.42,
        duration_s=5.5,
        kind="sim_only",
    )


@mock_aws
def test_snapshot_lands_on_dated_key_and_latest_pointer(snapshot):
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="snaps", CreateBucketConfiguration={"LocationConstraint": REGION})
    store = SnapshotStore(bucket="snaps", region=REGION)

    key = store.put_snapshot(snapshot, as_of=AS_OF)

    assert key == "snapshots/2026/06/17/run-20260617.json"
    dated = json.loads(s3.get_object(Bucket="snaps", Key=key)["Body"].read())
    latest = json.loads(s3.get_object(Bucket="snaps", Key="latest.json")["Body"].read())
    assert dated == latest
    assert dated["run"]["run_id"] == "run-20260617"


@mock_aws
def test_run_index_round_trips_and_rerun_replaces():
    ensure_table(table_name=TABLE, region=REGION)
    index = RunIndex(table_name=TABLE, region=REGION)

    index.record_run(_record("2026-06-17T11:02:00+00:00"))
    index.record_run(_record("2026-06-17T15:30:00+00:00", status="failed"))

    runs = index.list_runs()
    assert len(runs) == 1
    assert runs[0].created_at == "2026-06-17T15:30:00+00:00"
    assert runs[0].status == "failed"
    assert runs[0].cost == pytest.approx(0.42)
    assert runs[0].duration_s == pytest.approx(5.5)


@mock_aws
def test_run_enabled_defaults_on_and_toggles():
    ensure_table(table_name=TABLE, region=REGION)
    index = RunIndex(table_name=TABLE, region=REGION)

    assert index.run_enabled() is True
    index.set_run_enabled(enabled=False)
    assert index.run_enabled() is False
    index.set_run_enabled(enabled=True)
    assert index.run_enabled() is True
