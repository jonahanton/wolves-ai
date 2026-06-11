from __future__ import annotations

import json

import pytest

from tests.fakes import FakeDynamoTable, FakeS3Client, build_test_app, client_for

RUN_ITEM = {
    "run_id": "agent-20260610-234149",
    "created_at": "2026-06-10T23:41:49Z",
    "s3_key": "snapshots/2026/06/10/agent-20260610-234149.json",
    "status": "completed",
    "cost": 0.21,
    "duration_s": 312,
    "kind": "agent",
}

EVENTS = (
    '{"kind": "llm_call", "ts": "2026-06-10T23:41:51Z"}\n'
    '{"kind": "llm_call", "ts": "2026-06-10T23:42:00Z"}\n'
    '{"kind": "tool_call", "ts": "2026-06-10T23:41:55Z"}\n'
)

ARTIFACT_INDEX = json.dumps(
    {
        "run_id": "agent-20260610-234149",
        "records": [
            {
                "id": "quant-001",
                "kind": "quant",
                "summary": "Baseline digest computed.",
                "created_at": "2026-06-10T23:41:51Z",
                "created_by": "quant-baseline",
            }
        ],
    }
)


async def test_run_list_maps_dynamo_items_to_camel_case_wire_records():
    dynamo = FakeDynamoTable(run_items=[RUN_ITEM])
    async with client_for(build_test_app(dynamo=dynamo)) as client:
        response = await client.get("/runs")
    assert response.status_code == 200
    assert response.json() == {
        "runs": [
            {
                "runId": "agent-20260610-234149",
                "createdAt": "2026-06-10T23:41:49Z",
                "s3Key": "snapshots/2026/06/10/agent-20260610-234149.json",
                "status": "completed",
                "cost": 0.21,
                "durationS": 312.0,
                "kind": "agent",
            }
        ]
    }


async def test_detail_summarises_events_and_artifacts_alongside_the_record():
    dynamo = FakeDynamoTable(run_items=[RUN_ITEM])
    s3 = FakeS3Client(
        {
            "runs/agent-20260610-234149/journal.md": "# Journal",
            "runs/agent-20260610-234149/events.jsonl": EVENTS,
            "runs/agent-20260610-234149/artifacts/index.json": ARTIFACT_INDEX,
        }
    )
    async with client_for(build_test_app(dynamo=dynamo, s3=s3)) as client:
        response = await client.get("/runs/agent-20260610-234149")
    assert response.status_code == 200
    body = response.json()
    assert body["record"]["cost"] == 0.21
    assert body["hasJournal"] is True
    assert body["events"] == {
        "count": 3,
        "kinds": {"llm_call": 2, "tool_call": 1},
        "firstTs": "2026-06-10T23:41:51Z",
        "lastTs": "2026-06-10T23:42:00Z",
    }
    assert body["artifacts"] == [
        {
            "id": "quant-001",
            "kind": "quant",
            "summary": "Baseline digest computed.",
            "createdAt": "2026-06-10T23:41:51Z",
            "createdBy": "quant-baseline",
        }
    ]


async def test_detail_without_record_or_files_is_404():
    async with client_for(build_test_app(s3=FakeS3Client())) as client:
        response = await client.get("/runs/agent-20990101-000000")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("/runs/agent-20260610-234149/journal", "text/markdown; charset=utf-8"),
        ("/runs/agent-20260610-234149/events", "application/x-ndjson"),
        ("/runs/agent-20260610-234149/artifacts/quant-001", "application/json"),
    ],
)
async def test_run_files_are_served_raw_with_their_media_type(path, media_type):
    s3 = FakeS3Client(
        {
            "runs/agent-20260610-234149/journal.md": "# Journal",
            "runs/agent-20260610-234149/events.jsonl": EVENTS,
            "runs/agent-20260610-234149/artifacts/quant-001.json": '{"id": "quant-001"}',
        }
    )
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
