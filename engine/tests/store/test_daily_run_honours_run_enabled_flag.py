from __future__ import annotations

import json
from datetime import date

import boto3
from moto import mock_aws

from wolves.config import Settings
from wolves.daily import daily_run
from wolves.store.init import ensure_table
from wolves.store.store import RunIndex

REGION = "eu-west-2"
TABLE = "wolves-forecaster"
AS_OF = date(2026, 6, 17)


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(snapshot_dir=tmp_path / "runs", aws_region=REGION, dynamo_table=TABLE, **overrides)


@mock_aws
def test_disabled_flag_skips_the_run(tmp_path):
    ensure_table(table_name=TABLE, region=REGION)
    boto3.client("s3", region_name=REGION).create_bucket(
        Bucket="snaps", CreateBucketConfiguration={"LocationConstraint": REGION}
    )
    RunIndex(table_name=TABLE, region=REGION).set_run_enabled(enabled=False)
    settings = _settings(tmp_path, snapshot_bucket="snaps")

    assert daily_run(settings, as_of=AS_OF, n_sims=100) is False
    assert not (tmp_path / "runs").exists()


@mock_aws
def test_enabled_run_writes_local_s3_and_index_idempotently(tmp_path):
    ensure_table(table_name=TABLE, region=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket="snaps", CreateBucketConfiguration={"LocationConstraint": REGION})
    settings = _settings(tmp_path, snapshot_bucket="snaps")

    assert daily_run(settings, as_of=AS_OF, n_sims=100) is True
    assert daily_run(settings, as_of=AS_OF, n_sims=100) is True

    local = json.loads((tmp_path / "runs" / "run-20260617.json").read_text())
    assert local["run"]["run_id"] == "run-20260617"
    stored = json.loads(s3.get_object(Bucket="snaps", Key="snapshots/2026/06/17/run-20260617.json")["Body"].read())
    assert stored["run"]["run_id"] == "run-20260617"

    runs = RunIndex(table_name=TABLE, region=REGION).list_runs()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].s3_key == "snapshots/2026/06/17/run-20260617.json"


def test_unreachable_table_downgrades_to_local_run(tmp_path):
    settings = _settings(tmp_path, dynamo_endpoint="http://127.0.0.1:9")

    assert daily_run(settings, as_of=AS_OF, n_sims=100) is True
    assert (tmp_path / "runs" / "latest.json").exists()
