from __future__ import annotations

import json
from datetime import date

import boto3
import pytest
from moto import mock_aws

from wolves.config import Settings
from wolves.run import generate_snapshot
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.snapshots import SnapshotStore
from wolves.snapshot import Snapshot

REGION = "eu-west-2"
AS_OF = date(2026, 6, 17)


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    settings = Settings(runs_root=tmp_path_factory.mktemp("clobber-runs"), storage_mode="local")
    snapshot, _ = generate_snapshot(settings, n_sims=200, seed=7, run_id="run-20260617")
    return snapshot


def _variant(base: Snapshot, *, run_id: str, kind: str, created_at: str) -> Snapshot:
    return base.model_copy(
        update={"run": base.run.model_copy(update={"run_id": run_id, "kind": kind, "created_at": created_at})}
    )


def _latest_run_id(s3) -> str:
    body = s3.get_object(Bucket="snaps", Key="snapshots/latest.json")["Body"].read()
    return json.loads(body)["run"]["run_id"]


EARLY = "2026-06-17T10:00:00+00:00"
LATE = "2026-06-17T18:00:00+00:00"


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        # A later sim_only must not displace a richer agent snapshot.
        (("agent-1", "agent", EARLY), ("sim-1", "sim_only", LATE), "agent-1"),
        # Priority beats recency regardless of write order.
        (("sim-1", "sim_only", LATE), ("agent-1", "agent", EARLY), "agent-1"),
        # A live refit folds in new results and supersedes an earlier agent run.
        (("agent-1", "agent", EARLY), ("live-1", "live", LATE), "live-1"),
    ],
)
@mock_aws
def test_latest_pointer_respects_kind_priority(base, tmp_path, first, second, expected):
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="snaps", CreateBucketConfiguration={"LocationConstraint": REGION})
    store = SnapshotStore(ArtifactStore(Settings(bucket="snaps", storage_mode="s3", runs_root=tmp_path)))

    store.put_snapshot(_variant(base, run_id=first[0], kind=first[1], created_at=first[2]), as_of=AS_OF)
    store.put_snapshot(_variant(base, run_id=second[0], kind=second[1], created_at=second[2]), as_of=AS_OF)

    assert _latest_run_id(s3) == expected
