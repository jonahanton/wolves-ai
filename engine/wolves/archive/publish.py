"""Publish a verified archive bundle without replacing existing objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import boto3
from botocore.config import Config

from wolves.archive.contracts import ArchiveManifest
from wolves.archive.preserve import put_if_absent
from wolves.archive.verify import verify_archive
from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger(__name__)


def release_digest(root: Path) -> str:
    """Return a content-derived identifier covering every release file."""
    entries = [
        (
            path.relative_to(root).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(
            (item for item in root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    ]
    body = json.dumps(entries, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def publish_archive(
    root: Path,
    *,
    bucket: str,
    region: str | None,
    destination_prefix: str,
) -> str:
    """Upload a verified archive beneath a content-addressed release prefix."""
    manifest_body = (root / "manifest.json").read_bytes()
    manifest = ArchiveManifest.model_validate_json(manifest_body)
    verify_archive(root, manifest)
    release = release_digest(root)
    prefix = f"{destination_prefix.strip('/')}/{release}"
    client = boto3.client("s3", region_name=region, config=Config(max_pool_connections=16))
    paths = sorted(
        (item for item in root.rglob("*") if item.is_file() and item.name != "manifest.json"),
        key=lambda item: item.relative_to(root).as_posix(),
    )
    paths.append(root / "manifest.json")
    for path in paths:
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        key = f"{prefix}/{path.relative_to(root).as_posix()}"
        put_if_absent(client, bucket=bucket, key=key, body=body, digest=digest)
    return prefix


def main() -> None:
    """Publish a static archive release."""
    configure_cli_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region")
    parser.add_argument("--destination-prefix", default="static-archive/releases")
    args = parser.parse_args()
    prefix = publish_archive(
        args.root,
        bucket=args.bucket,
        region=args.region,
        destination_prefix=args.destination_prefix,
    )
    logger.info("published verified archive to s3://%s/%s", args.bucket, prefix)


if __name__ == "__main__":
    main()
