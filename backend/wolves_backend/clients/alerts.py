from __future__ import annotations

import logging
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)

PUBLISH_INTERVAL_S = 3600.0


class Alerts:
    """SNS publisher for in-process job failures; a repeating failure alerts
    at most once an hour per job, and no topic means log-only."""

    def __init__(self, *, topic_arn: str, region: str, client: Any | None = None) -> None:
        self._topic_arn = topic_arn
        self._client = client or (boto3.client("sns", region_name=region) if topic_arn else None)
        self._last_published: dict[str, float] = {}

    def publish(self, job: str, message: str) -> None:
        if self._client is None or not self._topic_arn:
            return
        now = time.monotonic()
        last = self._last_published.get(job)
        if last is not None and now - last < PUBLISH_INTERVAL_S:
            return
        self._last_published[job] = now
        try:
            self._client.publish(TopicArn=self._topic_arn, Subject=f"wolves backend job failed: {job}", Message=message)
        except Exception:
            logger.exception("alert publish failed for %s", job)
