from __future__ import annotations

from tests.fakes import ADMIN_HEADERS, FakeEcsClient, build_test_app, client_for

ACTIVE_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/aaa111"
NEW_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/bbb222"


async def test_run_now_returns_409_while_a_run_is_active():
    ecs = FakeEcsClient(task_arn=NEW_ARN, active_tasks=[{"taskArn": ACTIVE_ARN, "lastStatus": "RUNNING"}])
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now")
    assert response.status_code == 409
    assert ecs.run_calls == []


async def test_force_overrides_the_active_run_guard():
    ecs = FakeEcsClient(task_arn=NEW_ARN, active_tasks=[{"taskArn": ACTIVE_ARN, "lastStatus": "RUNNING"}])
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now", json={"force": True})
    assert response.status_code == 202
    assert response.json() == {"taskArn": NEW_ARN}


async def test_run_now_proceeds_when_nothing_is_active():
    ecs = FakeEcsClient(task_arn=NEW_ARN)
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/run-now")
    assert response.status_code == 202
