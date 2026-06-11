from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from wolves_backend.errors import UpstreamError
from wolves_backend.models import ActiveRun


class EngineTasks:
    """One-off ECS task control for the forecasting engine."""

    def __init__(
        self,
        *,
        cluster_arn: str,
        task_definition: str,
        extra_task_families: tuple[str, ...] = (),
        subnets: list[str],
        security_group: str,
        region: str,
        client: Any | None = None,
    ) -> None:
        self._cluster_arn = cluster_arn
        self._task_definition = task_definition
        self._families = [task_definition, *(family for family in extra_task_families if family)]
        self._subnets = subnets
        self._security_group = security_group
        self._client = client or boto3.client("ecs", region_name=region)

    def run_now(self, *, command: list[str] | None = None, environment: dict[str, str] | None = None) -> str:
        """Launch one engine task and return its ARN."""
        overrides = _container_overrides(command=command, environment=environment)
        kwargs: dict[str, Any] = {
            "cluster": self._cluster_arn,
            "taskDefinition": self._task_definition,
            "launchType": "FARGATE",
            "count": 1,
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": self._subnets,
                    "securityGroups": [self._security_group] if self._security_group else [],
                    "assignPublicIp": "ENABLED",
                }
            },
        }
        if overrides:
            kwargs["overrides"] = overrides
        try:
            result = self._client.run_task(**kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("ecs", str(exc)) from exc
        tasks = result.get("tasks") or []
        if not tasks or not tasks[0].get("taskArn"):
            failures = result.get("failures") or []
            reason = failures[0].get("reason") if failures else None
            raise UpstreamError("ecs", reason or "RunTask returned no task")
        return tasks[0]["taskArn"]

    def list_active(self) -> list[ActiveRun]:
        """Return engine tasks not yet stopped; desiredStatus RUNNING also
        matches tasks still provisioning."""
        try:
            arns: list[str] = []
            for family in self._families:
                listed = self._client.list_tasks(cluster=self._cluster_arn, family=family, desiredStatus="RUNNING")
                arns.extend(listed.get("taskArns") or [])
            if not arns:
                return []
            described = self._client.describe_tasks(cluster=self._cluster_arn, tasks=arns)
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("ecs", str(exc)) from exc
        return [
            ActiveRun(
                task_arn=task["taskArn"],
                last_status=task.get("lastStatus", ""),
                started_at=task["startedAt"].isoformat() if task.get("startedAt") else None,
            )
            for task in described.get("tasks") or []
        ]

    def stop(self, task_arn: str) -> None:
        try:
            self._client.stop_task(cluster=self._cluster_arn, task=task_arn, reason="Stopped from admin")
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("ecs", str(exc)) from exc


def _container_overrides(
    *, command: list[str] | None = None, environment: dict[str, str] | None = None
) -> dict[str, Any] | None:
    if not command and not environment:
        return None
    override: dict[str, Any] = {"name": "engine"}
    if command:
        override["command"] = command
    if environment:
        override["environment"] = [{"name": name, "value": value} for name, value in sorted(environment.items())]
    return {"containerOverrides": [override]}
