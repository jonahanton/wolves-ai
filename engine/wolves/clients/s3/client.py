"""Typed S3 adapter for one bucket. boto3 is synchronous by deliberate
choice: S3 calls bracket a run (state pull at start, snapshot and state
pushes at the end) and never sit inside the agent loop. Retries use
botocore's standard mode so throttling and transient faults are handled at
the transport layer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_MISSING_CODES = {"NoSuchKey", "404"}


class S3UnavailableError(Exception):
    """An S3 call failed after retries."""

    def __init__(self, bucket: str, operation: str) -> None:
        self.bucket = bucket
        self.operation = operation
        super().__init__(f"s3 {operation} failed for bucket {bucket!r}")


class S3Client:
    """Get, put and list text objects with retries and narrow errors."""

    def __init__(self, *, bucket: str, region: str) -> None:
        self.bucket = bucket
        config = Config(retries={"max_attempts": 5, "mode": "standard"})
        self._s3 = boto3.client("s3", region_name=region, config=config)

    def get_text(self, key: str) -> str | None:
        """Return the object body as text, or None when the key is absent."""
        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _MISSING_CODES:
                return None
            raise S3UnavailableError(self.bucket, "get_object") from exc
        except BotoCoreError as exc:
            raise S3UnavailableError(self.bucket, "get_object") from exc
        return response["Body"].read().decode("utf-8")

    def put_text(self, key: str, body: str, *, content_type: str = "text/plain; charset=utf-8") -> None:
        """Write the text body to the key."""
        self._guard(
            "put_object",
            lambda: self._s3.put_object(
                Bucket=self.bucket, Key=key, Body=body.encode("utf-8"), ContentType=content_type
            ),
        )

    def get_bytes(self, key: str) -> bytes | None:
        """Return the object body as bytes, or None when the key is absent."""
        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in _MISSING_CODES:
                return None
            raise S3UnavailableError(self.bucket, "get_object") from exc
        except BotoCoreError as exc:
            raise S3UnavailableError(self.bucket, "get_object") from exc
        return response["Body"].read()

    def put_bytes(self, key: str, body: bytes, *, content_type: str = "application/octet-stream") -> None:
        """Write the binary body to the key."""
        self._guard(
            "put_object",
            lambda: self._s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type),
        )

    def list_keys(self, *, prefix: str) -> list[str]:
        """Return every key under the prefix."""
        paginator = self._s3.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in self._guard("list_objects_v2", lambda: list(paginator.paginate(Bucket=self.bucket, Prefix=prefix))):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def _guard[T](self, operation: str, call: Callable[[], T]) -> T:
        try:
            return call()
        except (ClientError, BotoCoreError) as exc:
            raise S3UnavailableError(self.bucket, operation) from exc
