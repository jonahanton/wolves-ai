from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from wolves_backend.errors import UpstreamError


class EngineTasks:
    """One-off ECS task control for the forecasting engine."""

    def __init__(
        self,
        *,
        cluster_arn: str,
        task_definition: str,
        subnets: list[str],
        security_group: str,
        region: str,
        client: Any | None = None,
    ) -> None:
        self._cluster_arn = cluster_arn
        self._task_definition = task_definition
        self._subnets = subnets
        self._security_group = security_group
        self._client = client or boto3.client("ecs", region_name=region)

    def run_now(self) -> str:
        """Launch one engine task and return its ARN."""
        try:
            result = self._client.run_task(
                cluster=self._cluster_arn,
                taskDefinition=self._task_definition,
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": self._subnets,
                        "securityGroups": [self._security_group] if self._security_group else [],
                        "assignPublicIp": "ENABLED",
                    }
                },
            )
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("ecs", str(exc)) from exc
        tasks = result.get("tasks") or []
        if not tasks or not tasks[0].get("taskArn"):
            failures = result.get("failures") or []
            reason = failures[0].get("reason") if failures else None
            raise UpstreamError("ecs", reason or "RunTask returned no task")
        return tasks[0]["taskArn"]

    def stop(self, task_arn: str) -> None:
        try:
            self._client.stop_task(cluster=self._cluster_arn, task=task_arn, reason="Stopped from admin")
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("ecs", str(exc)) from exc
