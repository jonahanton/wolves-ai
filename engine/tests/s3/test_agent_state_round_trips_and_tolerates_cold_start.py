from __future__ import annotations

import boto3
from moto import mock_aws

from wolves.config import Settings
from wolves.s3.agent_state import build_agent_state_store

REGION = "eu-west-2"
BUCKET = "agent-state"
RUN_ID = "agent-20260617-101010"


def _settings(root, *, storage_mode: str = "both") -> Settings:
    return Settings(bucket=BUCKET, storage_mode=storage_mode, aws_region=REGION, runs_root=root)


def _create_bucket() -> None:
    boto3.client("s3", region_name=REGION).create_bucket(
        Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
    )


def test_local_mode_means_no_store(tmp_path):
    assert build_agent_state_store(_settings(tmp_path, storage_mode="local")) is None


@mock_aws
def test_cold_start_pull_finds_nothing_and_writes_nothing(tmp_path):
    _create_bucket()
    store = build_agent_state_store(_settings(tmp_path))
    assert store is not None

    assert store.pull() == 0
    assert not (tmp_path / "agent-state").exists()


@mock_aws
def test_push_then_pull_round_trips_lessons_journal_and_calibration(tmp_path):
    _create_bucket()
    source = tmp_path / "source"
    (source / "agent-state").mkdir(parents=True)
    (source / "agent-state" / "lessons.jsonl").write_text('{"date": "2026-06-17", "text": "market beats priors"}\n')
    (source / "agent-state" / "calibration.jsonl").write_text('{"match_id": "1"}\n')
    journal = source / "runs" / RUN_ID / "journal.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("### 2026-06-17T10:10:10\n\nKeeper fit.\n")

    pusher = build_agent_state_store(_settings(source))
    assert pusher is not None
    assert pusher.push(run_id=RUN_ID) == 3

    target = tmp_path / "target"
    puller = build_agent_state_store(_settings(target))
    assert puller is not None
    assert puller.pull() == 3
    for relative in ("agent-state/lessons.jsonl", "agent-state/calibration.jsonl", f"runs/{RUN_ID}/journal.md"):
        assert (target / relative).read_text() == (source / relative).read_text()


@mock_aws
def test_push_skips_files_that_do_not_exist_yet(tmp_path):
    _create_bucket()
    store = build_agent_state_store(_settings(tmp_path))
    assert store is not None

    assert store.push(run_id=RUN_ID) == 0


@mock_aws
def test_pull_hydrates_compact_market_series_without_raw_odds(tmp_path):
    _create_bucket()
    client = boto3.client("s3", region_name=REGION)
    client.put_object(Bucket=BUCKET, Key="odds-archive/2026-06-23/080000.series.json", Body=b"{}")
    client.put_object(Bucket=BUCKET, Key="odds-archive/2026-06-23/080000.json", Body=b"raw")
    store = build_agent_state_store(_settings(tmp_path))
    assert store is not None

    assert store.pull() == 1
    assert (tmp_path / "odds-archive/2026-06-23/080000.series.json").exists()
    assert not (tmp_path / "odds-archive/2026-06-23/080000.json").exists()
