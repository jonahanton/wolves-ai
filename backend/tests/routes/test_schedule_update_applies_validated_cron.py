from __future__ import annotations

import pytest

from tests.fakes import ADMIN_HEADERS, FakeSchedulerClient, build_test_app, client_for


async def test_cron_update_rewrites_schedule_expression():
    scheduler = FakeSchedulerClient()
    async with client_for(build_test_app(scheduler=scheduler), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/schedule", json={"enabled": True, "cron": "30 9 * * ? *"})
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "cron": "cron(30 9 * * ? *)"}
    assert scheduler.updates[0]["ScheduleExpression"] == "cron(30 9 * * ? *)"


async def test_omitted_cron_keeps_current_expression():
    scheduler = FakeSchedulerClient(cron="cron(0 11 * * ? *)")
    async with client_for(build_test_app(scheduler=scheduler), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/schedule", json={"enabled": True})
    assert response.json() == {"enabled": True, "cron": "cron(0 11 * * ? *)"}
    assert scheduler.updates[0]["ScheduleExpression"] == "cron(0 11 * * ? *)"


@pytest.mark.parametrize(
    "cron",
    [
        "0 11 * * ?",
        "0 11 * * ? * *",
        "0 11 * * ? $(rm)",
        "",
        "0;0 11 * * ? *",
    ],
)
async def test_invalid_cron_rejected_before_aws(cron):
    scheduler = FakeSchedulerClient()
    async with client_for(build_test_app(scheduler=scheduler), headers=ADMIN_HEADERS) as client:
        response = await client.post("/admin/schedule", json={"enabled": True, "cron": cron})
    assert response.status_code == 400
    assert scheduler.updates == []
