from __future__ import annotations

import pytest

from tests.fakes import ADMIN_HEADERS, FakeDynamoTable, FakeEcsClient, FakeSchedulerClient, build_test_app, client_for

TASK_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/abc123def456"


async def test_schedule_get_reflects_scheduler_state():
    scheduler = FakeSchedulerClient(state="DISABLED", cron="cron(0 11 * * ? *)")
    async with client_for(build_test_app(scheduler=scheduler), headers=ADMIN_HEADERS) as client:
        response = await client.get("/admin/schedule")
    assert response.json() == {"enabled": False, "cron": "0 11 * * ? *"}


async def test_schedule_disable_flips_scheduler_and_run_enabled_flag():
    scheduler = FakeSchedulerClient()
    dynamo = FakeDynamoTable()
    app = build_test_app(scheduler=scheduler, dynamo=dynamo)
    async with client_for(app, headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/schedule", json={"enabled": False})
    assert response.json() == {"enabled": False, "cron": "0 11 * * ? *"}
    assert scheduler.updates[0]["State"] == "DISABLED"
    assert dynamo.put_items[0] == {"PK": "CONTROL", "SK": "run_enabled", "enabled": False}


async def test_schedule_update_rejects_non_boolean():
    async with client_for(build_test_app(), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/schedule", json={"enabled": "yes"})
    assert response.status_code == 400


async def test_run_now_returns_task_arn_with_202():
    ecs = FakeEcsClient(task_arn=TASK_ARN)
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now")
    assert response.status_code == 202
    assert response.json() == {"taskArn": TASK_ARN}
    assert ecs.run_calls[0]["launchType"] == "FARGATE"
    assert ecs.run_calls[0]["networkConfiguration"]["awsvpcConfiguration"]["subnets"] == ["subnet-1", "subnet-2"]


@pytest.mark.parametrize(
    ("body", "command", "environment"),
    [
        ({"mode": "daily"}, ["wolves.run"], None),
        (
            {"mode": "agent", "ceilingUsd": 3.5},
            ["wolves.run_agent", "--live", "--confirm-spend"],
            [{"name": "AGENT_RUN_CEILING_USD", "value": "3.50"}],
        ),
        ({"mode": "live"}, ["wolves.live", "--loop", "--interval", "60"], None),
    ],
)
async def test_run_now_mode_sets_command_and_environment(body, command, environment):
    ecs = FakeEcsClient(task_arn=TASK_ARN)
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now", json=body)
    override = ecs.run_calls[0]["overrides"]["containerOverrides"][0]
    assert response.status_code == 202
    assert override["command"] == command
    assert override.get("environment") == environment


async def test_run_now_rejects_ceiling_on_non_agent_modes():
    ecs = FakeEcsClient(task_arn=TASK_ARN)
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now", json={"mode": "live", "ceilingUsd": 3.5})
    assert response.status_code == 400
    assert ecs.run_calls == []


async def test_run_now_failure_reason_maps_to_502():
    ecs = FakeEcsClient(failure_reason="RESOURCE:MEMORY")
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now")
    assert response.status_code == 502
    assert response.json() == {"error": "RESOURCE:MEMORY"}


async def test_stop_validates_task_arn():
    async with client_for(build_test_app(), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/stop", json={"taskArn": "not-an-arn"})
    assert response.status_code == 400


async def test_stop_sends_stop_task_for_valid_arn():
    ecs = FakeEcsClient(task_arn=TASK_ARN)
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/stop", json={"taskArn": TASK_ARN})
    assert response.json() == {"stopped": TASK_ARN}
    assert ecs.stop_calls[0]["task"] == TASK_ARN
