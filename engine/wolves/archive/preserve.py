"""Preserve every retained production source version by content hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger(__name__)
DEFAULT_PREFIXES = (
    "snapshots/",
    "live/results.json",
    "live/state.json",
    "live/impact.json",
    "live/history/",
    "runs/",
    "datasets/",
    "models/",
)


class ArchivePreservationError(ValueError):
    """A preserved object conflicts with its expected content."""


@dataclass(frozen=True)
class SourceVersion:
    key: str
    version_id: str
    last_modified: str
    size: int
    etag: str
    is_latest: bool


@dataclass(frozen=True)
class DeleteMarker:
    key: str
    version_id: str
    last_modified: str
    is_latest: bool


@dataclass(frozen=True)
class PreservedVersion:
    key: str
    version_id: str
    last_modified: str
    size: int
    etag: str
    is_latest: bool
    sha256: str
    archive_key: str


def inventory_versions(
    client: BaseClient,
    *,
    bucket: str,
    prefixes: tuple[str, ...],
) -> tuple[list[SourceVersion], list[DeleteMarker]]:
    """List every retained object version and delete marker."""
    versions: dict[tuple[str, str], SourceVersion] = {}
    markers: dict[tuple[str, str], DeleteMarker] = {}
    paginator = client.get_paginator("list_object_versions")
    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Versions", []):
                if not _matches_prefix(item["Key"], prefix):
                    continue
                version = SourceVersion(
                    key=item["Key"],
                    version_id=item["VersionId"],
                    last_modified=item["LastModified"].astimezone(UTC).isoformat(),
                    size=item["Size"],
                    etag=item["ETag"].strip('"'),
                    is_latest=item["IsLatest"],
                )
                versions[(version.key, version.version_id)] = version
            for item in page.get("DeleteMarkers", []):
                if not _matches_prefix(item["Key"], prefix):
                    continue
                marker = DeleteMarker(
                    key=item["Key"],
                    version_id=item["VersionId"],
                    last_modified=item["LastModified"].astimezone(UTC).isoformat(),
                    is_latest=item["IsLatest"],
                )
                markers[(marker.key, marker.version_id)] = marker
    return (
        sorted(versions.values(), key=lambda item: (item.key, item.last_modified, item.version_id)),
        sorted(markers.values(), key=lambda item: (item.key, item.last_modified, item.version_id)),
    )


def preserve_versions(
    client: BaseClient,
    *,
    bucket: str,
    destination_prefix: str,
    versions: list[SourceVersion],
    workers: int,
) -> list[PreservedVersion]:
    """Copy source versions into immutable content-addressed objects."""
    locks: dict[str, Lock] = {}
    locks_guard = Lock()

    def preserve(version: SourceVersion) -> PreservedVersion:
        response = client.get_object(Bucket=bucket, Key=version.key, VersionId=version.version_id)
        body = response["Body"].read()
        digest = hashlib.sha256(body).hexdigest()
        archive_key = f"{destination_prefix.rstrip('/')}/sha256/{digest[:2]}/{digest}"
        with locks_guard:
            digest_lock = locks.setdefault(digest, Lock())
        with digest_lock:
            put_if_absent(client, bucket=bucket, key=archive_key, body=body, digest=digest)
        return PreservedVersion(**asdict(version), sha256=digest, archive_key=archive_key)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(preserve, versions))


def write_inventory(
    client: BaseClient,
    *,
    bucket: str,
    destination_prefix: str,
    versions: list[PreservedVersion],
    delete_markers: list[DeleteMarker],
    local_output: Path | None,
) -> str:
    """Write the checksum inventory after every content object is durable."""
    document = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_bucket": bucket,
        "versions": [asdict(version) for version in versions],
        "delete_markers": [asdict(marker) for marker in delete_markers],
    }
    body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(body).hexdigest()
    key = f"{destination_prefix.rstrip('/')}/inventories/{digest}.json"
    put_if_absent(client, bucket=bucket, key=key, body=body, digest=digest)
    if local_output is not None:
        local_output.parent.mkdir(parents=True, exist_ok=True)
        local_output.write_bytes(body)
    return key


def put_if_absent(client: BaseClient, *, bucket: str, key: str, body: bytes, digest: str) -> None:
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json" if key.endswith(".json") else "application/octet-stream",
            Metadata={"sha256": digest},
            IfNoneMatch="*",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
            raise
        existing = client.head_object(Bucket=bucket, Key=key)
        if existing["ContentLength"] != len(body) or existing.get("Metadata", {}).get("sha256") != digest:
            raise ArchivePreservationError(f"archive object collision at {key}") from exc


def _matches_prefix(key: str, prefix: str) -> bool:
    return key.startswith(prefix) if prefix.endswith("/") else key == prefix


def main() -> None:
    """Preserve versioned archive sources without mutating existing keys."""
    configure_cli_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region")
    parser.add_argument("--destination-prefix", default="static-archive/source")
    parser.add_argument("--local-inventory", type=Path)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be greater than zero")
    client = boto3.client(
        "s3",
        region_name=args.region,
        config=Config(max_pool_connections=args.workers),
    )
    versions, markers = inventory_versions(client, bucket=args.bucket, prefixes=DEFAULT_PREFIXES)
    logger.info(
        "inventoried %s retained versions (%s bytes) and %s delete markers",
        len(versions),
        sum(version.size for version in versions),
        len(markers),
    )
    if not args.execute:
        return
    preserved = preserve_versions(
        client,
        bucket=args.bucket,
        destination_prefix=args.destination_prefix,
        versions=versions,
        workers=args.workers,
    )
    inventory_key = write_inventory(
        client,
        bucket=args.bucket,
        destination_prefix=args.destination_prefix,
        versions=preserved,
        delete_markers=markers,
        local_output=args.local_inventory,
    )
    logger.info("preserved %s versions; inventory %s", len(preserved), inventory_key)


if __name__ == "__main__":
    main()
