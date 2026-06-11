from __future__ import annotations

import pytest

from tests.fakes import FakeS3Client, build_test_app, client_for

FAMILIES = [
    ("lessons", "agent-state/lessons.jsonl"),
    ("scenarios", "agent-state/scenarios.jsonl"),
    ("sources-seen", "agent-state/sources_seen.jsonl"),
    ("relevance-feedback", "agent-state/relevance_feedback.jsonl"),
    ("calibration", "agent-state/calibration.jsonl"),
]


@pytest.mark.parametrize(("name", "key"), FAMILIES)
async def test_each_family_maps_to_its_jsonl_key(name, key):
    s3 = FakeS3Client({key: '{"line": 1}\n'})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get(f"/agent-state/{name}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"
    assert response.text == '{"line": 1}\n'


async def test_unknown_family_is_404():
    async with client_for(build_test_app(s3=FakeS3Client())) as client:
        response = await client.get("/agent-state/secrets")
    assert response.status_code == 404
    assert response.json() == {"error": "unknown agent state"}
