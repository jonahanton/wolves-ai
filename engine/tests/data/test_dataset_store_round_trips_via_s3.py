from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from wolves.config import Settings
from wolves.data.contracts import DatasetManifest
from wolves.data.store import DatasetNotFoundError, DatasetStore, dataset_filename

MANIFEST = DatasetManifest(
    dataset_id="abc123def456", built_at="now", engine_version="0", tables={"matches": 1}, source_hashes={}
)


def _bucket() -> None:
    boto3.client("s3", region_name="eu-west-2").create_bucket(
        Bucket="bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
    )


@mock_aws
def test_publish_then_fresh_container_fetch_resolves_latest(tmp_path) -> None:
    _bucket()
    build_side = Settings(bucket="bucket", storage_mode="both", runs_root=tmp_path / "build")
    built_dir = tmp_path / "build" / "datasets"
    built_dir.mkdir(parents=True)
    (built_dir / dataset_filename(MANIFEST.dataset_id)).write_bytes(b"\x00binary\xff")

    DatasetStore(build_side).publish(built_dir, MANIFEST)

    fresh = Settings(bucket="bucket", storage_mode="both", runs_root=tmp_path / "fresh")
    path, manifest = DatasetStore(fresh).fetch()

    assert path.read_bytes() == b"\x00binary\xff"
    assert manifest.dataset_id == MANIFEST.dataset_id
    # Hydrated copy survives the bucket: a second fetch never touches S3.
    boto3.client("s3", region_name="eu-west-2").delete_object(
        Bucket="bucket", Key=f"datasets/{dataset_filename(MANIFEST.dataset_id)}"
    )
    assert DatasetStore(fresh).fetch(dataset_id=MANIFEST.dataset_id)[0].read_bytes() == b"\x00binary\xff"


@mock_aws
def test_fetch_of_unknown_dataset_raises(tmp_path) -> None:
    _bucket()
    settings = Settings(bucket="bucket", storage_mode="both", runs_root=tmp_path)

    with pytest.raises(DatasetNotFoundError):
        DatasetStore(settings).fetch(dataset_id="missing000000")
