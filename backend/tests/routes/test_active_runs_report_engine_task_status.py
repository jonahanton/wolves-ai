from __future__ import annotations

from datetime import UTC, datetime

from tests.fakes import ADMIN_HEADERS, AGENT_FAMILY, DAILY_FAMILY, FakeEcsClient, build_test_app, client_for

TASK_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/abc123def456"


async def test_active_runs_describe_running_engine_tasks_across_both_families():
    ecs = FakeEcsClient(
        active_tasks=[
            {
                "taskArn": TASK_ARN,
                "lastStatus": "RUNNING",
                "startedAt": datetime(2026, 6, 10, 11, 0, 5, tzinfo=UTC),
            },
            {"taskArn": f"{TASK_ARN}0", "lastStatus": "PROVISIONING", "family": AGENT_FAMILY},
        ]
    )
    async with client_for(build_test_app(ecs=ecs), headers=ADMIN_HEADERS) as client:
        response = await client.get("/admin/runs/active")
    assert response.status_code == 200
    assert response.json() == {
        "tasks": [
            {"taskArn": TASK_ARN, "lastStatus": "RUNNING", "startedAt": "2026-06-10T11:00:05+00:00"},
            {"taskArn": f"{TASK_ARN}0", "lastStatus": "PROVISIONING", "startedAt": None},
        ]
    }
    cluster = "arn:aws:ecs:eu-west-2:000000000000:cluster/wolves"
    assert ecs.list_calls == [
        {"cluster": cluster, "family": DAILY_FAMILY, "desiredStatus": "RUNNING"},
        {"cluster": cluster, "family": AGENT_FAMILY, "desiredStatus": "RUNNING"},
    ]


async def test_no_active_tasks_returns_empty_list():
    async with client_for(build_test_app(ecs=FakeEcsClient()), headers=ADMIN_HEADERS) as client:
        response = await client.get("/admin/runs/active")
    assert response.json() == {"tasks": []}
