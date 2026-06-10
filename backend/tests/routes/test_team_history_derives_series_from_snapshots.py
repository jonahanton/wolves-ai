from __future__ import annotations

import json

from tests.fakes import FakeS3Client, build_test_app, client_for


def snapshot_body(team_id: str, champion_prob: float) -> str:
    return json.dumps(
        {"teams": [{"team_id": team_id, "champion_prob": champion_prob, "reach_probs": {"SF": champion_prob * 2}}]}
    )


async def test_history_extracts_the_team_series_oldest_first():
    s3 = FakeS3Client(
        {
            "snapshots/2026/06/09/run-20260609.json": snapshot_body("ENG", 0.07),
            "snapshots/2026/06/10/agent-20260610-234149.json": snapshot_body("ENG", 0.09),
        }
    )
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/ENG/history")
    assert response.status_code == 200
    assert response.json() == {
        "teamId": "ENG",
        "points": [
            {"runId": "run-20260609", "asOf": "2026-06-09", "championProb": 0.07, "reachProbs": {"SF": 0.14}},
            {
                "runId": "agent-20260610-234149",
                "asOf": "2026-06-10",
                "championProb": 0.09,
                "reachProbs": {"SF": 0.18},
            },
        ],
    }


async def test_history_for_an_unknown_team_is_404():
    s3 = FakeS3Client({"snapshots/2026/06/09/run-20260609.json": snapshot_body("ENG", 0.07)})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/XYZ/history")
    assert response.status_code == 404


async def test_history_limit_keeps_only_the_newest_snapshots():
    s3 = FakeS3Client(
        {
            "snapshots/2026/06/08/run-20260608.json": snapshot_body("ENG", 0.05),
            "snapshots/2026/06/09/run-20260609.json": snapshot_body("ENG", 0.07),
            "snapshots/2026/06/10/run-20260610.json": snapshot_body("ENG", 0.09),
        }
    )
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/ENG/history", params={"limit": 2})
    assert [point["runId"] for point in response.json()["points"]] == ["run-20260609", "run-20260610"]
