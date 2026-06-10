from __future__ import annotations

import boto3
from moto import mock_aws

from wolves.config import Settings
from wolves.store.agent_state import build_agent_state_store

REGION = "eu-west-2"
BUCKET = "agent-state"


def _settings(root, *, bucket: str = BUCKET) -> Settings:
    return Settings(
        agent_state_bucket=bucket,
        aws_region=REGION,
        runs_root=root,
        lessons_path=root / "LESSONS.md",
        calibration_path=root / "calibration.jsonl",
    )


def _create_bucket() -> None:
    boto3.client("s3", region_name=REGION).create_bucket(
        Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
    )


def test_no_bucket_configured_means_no_store(tmp_path):
    assert build_agent_state_store(_settings(tmp_path, bucket="")) is None


@mock_aws
def test_cold_start_pull_finds_nothing_and_writes_nothing(tmp_path):
    _create_bucket()
    store = build_agent_state_store(_settings(tmp_path))
    assert store is not None

    assert store.pull() == 0
    assert not (tmp_path / "LESSONS.md").exists()
    assert not (tmp_path / "calibration.jsonl").exists()


@mock_aws
def test_push_then_pull_round_trips_lessons_journal_and_calibration(tmp_path):
    _create_bucket()
    source = tmp_path / "source"
    source.mkdir()
    (source / "LESSONS.md").write_text("## 2026-06-17\n\nMarket beats priors early.\n")
    (source / "calibration.jsonl").write_text('{"match_id": "1"}\n')
    journal = source / "agent-20260617-101010" / "journal.md"
    journal.parent.mkdir()
    journal.write_text("### 2026-06-17T10:10:10\n\nKeeper fit.\n")

    pusher = build_agent_state_store(_settings(source))
    assert pusher is not None
    assert pusher.push(run_id="agent-20260617-101010") == 3

    target = tmp_path / "target"
    puller = build_agent_state_store(_settings(target))
    assert puller is not None
    assert puller.pull() == 3
    assert (target / "LESSONS.md").read_text() == (source / "LESSONS.md").read_text()
    assert (target / "calibration.jsonl").read_text() == (source / "calibration.jsonl").read_text()
    assert (target / "agent-20260617-101010" / "journal.md").read_text() == journal.read_text()


@mock_aws
def test_push_skips_files_that_do_not_exist_yet(tmp_path):
    _create_bucket()
    store = build_agent_state_store(_settings(tmp_path))
    assert store is not None

    assert store.push(run_id="agent-20260617-101010") == 0
