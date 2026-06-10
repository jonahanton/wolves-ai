from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from wolves.config import Settings
from wolves.data.contracts import DatasetManifest
from wolves.data.store import DatasetNotFoundError, DatasetStore

MANIFEST = DatasetManifest(version="v9", built_at="now", engine_version="0", tables={"matches": 1}, source_hashes={})


@mock_aws
def test_publish_then_fetch_returns_identical_bytes_and_caches(tmp_path) -> None:
    boto3.client("s3", region_name="eu-west-2").create_bucket(
        Bucket="bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
    )
    settings = Settings(agent_state_bucket="bucket", runs_root=tmp_path / "fetch-side")
    built_dir = tmp_path / "build-side"
    built_dir.mkdir()
    (built_dir / "wolves-data-v9.duckdb").write_bytes(b"\x00binary\xff")
    (built_dir / "wolves-data-v9.duckdb.manifest.json").write_text(MANIFEST.model_dump_json(), encoding="utf-8")

    store = DatasetStore(settings)
    store.publish(built_dir, version="v9")
    path, manifest = store.fetch(version="v9")

    assert path.read_bytes() == b"\x00binary\xff"
    assert manifest.tables == {"matches": 1}
    # Cached copy must survive the bucket: a second fetch never touches S3.
    boto3.client("s3", region_name="eu-west-2").delete_object(Bucket="bucket", Key="datasets/wolves-data-v9.duckdb")
    assert store.fetch(version="v9")[0].read_bytes() == b"\x00binary\xff"


@mock_aws
def test_fetch_of_unknown_version_raises(tmp_path) -> None:
    boto3.client("s3", region_name="eu-west-2").create_bucket(
        Bucket="bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
    )
    settings = Settings(agent_state_bucket="bucket", runs_root=tmp_path)

    with pytest.raises(DatasetNotFoundError):
        DatasetStore(settings).fetch(version="v404")
