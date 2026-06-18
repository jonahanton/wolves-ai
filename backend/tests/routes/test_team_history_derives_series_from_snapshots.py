from __future__ import annotations

import json

from tests.fakes import FakeS3Client, build_test_app, client_for


def snapshot_body(team_id: str, champion_prob: float, *, markets: dict | None = None) -> str:
    body = {"teams": [{"team_id": team_id, "champion_prob": champion_prob, "reach_probs": {"SF": champion_prob * 2}}]}
    if markets is not None:
        body["markets"] = markets
    return json.dumps(body)


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
            {
                "runId": "run-20260609",
                "asOf": "2026-06-09",
                "championProb": 0.07,
                "reachProbs": {"SF": 0.14},
                "marketProb": None,
                "blendProb": None,
            },
            {
                "runId": "agent-20260610-234149",
                "asOf": "2026-06-10",
                "championProb": 0.09,
                "reachProbs": {"SF": 0.18},
                "marketProb": None,
                "blendProb": None,
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


async def test_history_carries_market_and_blend_probs_when_published():
    markets = {"market_probs": {"ENG": 0.108}, "blend_probs": {"ENG": 0.097}}
    s3 = FakeS3Client({"snapshots/2026/06/09/run-20260609.json": snapshot_body("ENG", 0.07, markets=markets)})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/ENG/history")
    point = response.json()["points"][0]
    assert point["marketProb"] == 0.108
    assert point["blendProb"] == 0.097


def two_team_body(champ: dict[str, float]) -> str:
    teams = [{"team_id": tid, "champion_prob": prob, "reach_probs": {"SF": prob * 2}} for tid, prob in champ.items()]
    return json.dumps({"teams": teams})


async def test_histories_batch_returns_each_requested_team():
    s3 = FakeS3Client(
        {
            "snapshots/2026/06/09/run-20260609.json": two_team_body({"ENG": 0.07, "FRA": 0.11}),
            "snapshots/2026/06/10/agent-20260610.json": two_team_body({"ENG": 0.09, "FRA": 0.12}),
        }
    )
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/histories", params={"ids": "ENG,FRA"})
    assert response.status_code == 200
    histories = {h["teamId"]: [p["championProb"] for p in h["points"]] for h in response.json()["histories"]}
    assert histories == {"ENG": [0.07, 0.09], "FRA": [0.11, 0.12]}


async def test_histories_batch_keeps_unknown_team_with_empty_points():
    s3 = FakeS3Client({"snapshots/2026/06/09/run-20260609.json": two_team_body({"ENG": 0.07})})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/teams/histories", params={"ids": "ENG,XYZ"})
    histories = {h["teamId"]: h["points"] for h in response.json()["histories"]}
    assert histories["XYZ"] == []
    assert len(histories["ENG"]) == 1
