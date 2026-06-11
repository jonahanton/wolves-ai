from __future__ import annotations

import json

import pytest

from tests.fakes import ADMIN_HEADERS, FakeDynamoTable, FakeEcsClient, build_test_app, client_for

TASK_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/abc123def456"

MUTATIONS = [
    ("/admin/run-now", None, "run-now", {"taskArn": TASK_ARN, "force": False, "mode": "daily", "ceilingUsd": None}),
    ("/admin/stop", {"taskArn": TASK_ARN}, "stop", {"taskArn": TASK_ARN}),
    ("/admin/schedule", {"enabled": True, "cron": "0 11 * * ? *"}, "schedule-update", None),
]


@pytest.mark.parametrize(("path", "body", "action", "payload"), MUTATIONS)
async def test_mutation_writes_audit_item(path, body, action, payload):
    dynamo = FakeDynamoTable()
    app = build_test_app(dynamo=dynamo, ecs=FakeEcsClient(task_arn=TASK_ARN))
    async with client_for(app, headers=ADMIN_HEADERS) as client:
        response = await client.post(path, json=body)
    assert response.status_code in (200, 202)
    audit_items = [item for item in dynamo.put_items if item["PK"] == "AUDIT"]
    assert len(audit_items) == 1
    item = audit_items[0]
    assert item["SK"].endswith(f"#{action}")
    assert item["action"] == action
    assert item["actor"] == "admin-token"
    assert item["ttl"] > 0
    if payload is not None:
        assert json.loads(item["payload"]) == payload


async def test_schedule_read_writes_no_audit_item():
    dynamo = FakeDynamoTable()
    async with client_for(build_test_app(dynamo=dynamo), headers=ADMIN_HEADERS) as client:
        await client.get("/admin/schedule")
    assert dynamo.put_items == []
