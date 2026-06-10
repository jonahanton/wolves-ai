"""boto3 is synchronous by deliberate choice, matching the engine's store
adapters: every call is wrapped in a thread at the route boundary, so an
async client buys nothing."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from wolves_backend.errors import UpstreamError


class SnapshotBucket:
    """Read-only access to published snapshots in S3."""

    def __init__(self, *, bucket: str, region: str, client: Any | None = None) -> None:
        self._bucket = bucket
        self._client = client or boto3.client("s3", region_name=region)

    def get(self, key: str) -> str | None:
        """Fetch an object body as text; a missing key returns None."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                return None
            raise UpstreamError("s3", str(exc)) from exc
        except BotoCoreError as exc:
            raise UpstreamError("s3", str(exc)) from exc
        return response["Body"].read().decode("utf-8")
