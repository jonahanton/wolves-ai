"""Run the static archive exporter or source audit."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from wolves.archive.export import audit_archive, default_days, export_archive
from wolves.archive.source import (
    ArchiveSource,
    LocalArchiveSource,
    S3ArchiveSource,
    complete_snapshots,
    load_dynamo_run_records,
)
from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger(__name__)


def parse_day_range(value: str) -> list[str]:
    """Expand a YYYY-MM-DD or inclusive YYYY-MM-DD:YYYY-MM-DD range."""
    parts = value.split(":", maxsplit=1)
    try:
        start = date.fromisoformat(parts[0])
        end = date.fromisoformat(parts[-1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("days must use YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD") from exc
    if end < start:
        raise argparse.ArgumentTypeError("archive day range ends before it starts")
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def source_from_argument(value: str, *, region: str | None) -> ArchiveSource:
    """Build a local or S3 archive source from a CLI value."""
    if value.startswith("s3://"):
        bucket_and_prefix = value.removeprefix("s3://").split("/", maxsplit=1)
        prefix = bucket_and_prefix[1] if len(bucket_and_prefix) == 2 else ""
        return S3ArchiveSource(bucket_and_prefix[0], prefix=prefix, region=region)
    return LocalArchiveSource(Path(value))


def main() -> None:
    """Run the static archive exporter or source audit."""
    configure_cli_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="local run root or s3://bucket/prefix")
    parser.add_argument("--output", type=Path, help="directory receiving versioned archive output")
    parser.add_argument("--days", type=parse_day_range, help="archive day or inclusive range")
    parser.add_argument("--region", help="AWS region for S3 archive sources")
    parser.add_argument("--run-index-table", help="DynamoDB run index to include")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    source = source_from_argument(args.source, region=args.region)
    if args.days is None:
        complete, _ = complete_snapshots(source)
        days = default_days(complete)
    else:
        days = args.days
    if args.audit:
        logger.info("%s", audit_archive(source, days=days).model_dump_json())
        return
    if args.output is None:
        parser.error("--output is required unless --audit is set")
    run_records = (
        load_dynamo_run_records(table_name=args.run_index_table, region=args.region or "eu-west-2")
        if args.run_index_table
        else None
    )
    manifest = export_archive(source, output=args.output, days=days, run_records=run_records)
    logger.info(
        "wrote archive %s with %s days; final day %s",
        manifest.schema_hash[:12],
        len(manifest.days),
        manifest.final_day,
    )
