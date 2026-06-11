from __future__ import annotations

from tests.fakes import FakeS3Client, build_test_app, client_for


async def test_index_parses_dated_keys_skips_pointer_and_sorts_newest_first():
    s3 = FakeS3Client(
        {
            "snapshots/latest.json": "{}",
            "snapshots/2026/06/09/run-20260609.json": "{}",
            "snapshots/2026/06/10/agent-20260610-234149.json": "{}",
            "snapshots/2026/06/10/live-20260610-120000.json": "{}",
            "snapshots/2026/06/10/junk.txt": "x",
        }
    )
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/snapshots")
    assert response.status_code == 200
    assert response.json() == {
        "snapshots": [
            {
                "runId": "live-20260610-120000",
                "asOf": "2026-06-10",
                "kind": "live",
                "key": "snapshots/2026/06/10/live-20260610-120000.json",
            },
            {
                "runId": "agent-20260610-234149",
                "asOf": "2026-06-10",
                "kind": "agent",
                "key": "snapshots/2026/06/10/agent-20260610-234149.json",
            },
            {
                "runId": "run-20260609",
                "asOf": "2026-06-09",
                "kind": "run",
                "key": "snapshots/2026/06/09/run-20260609.json",
            },
        ]
    }


async def test_index_lists_the_local_runs_directory_when_no_bucket(tmp_path):
    day = tmp_path / "snapshots" / "2026" / "06" / "10"
    day.mkdir(parents=True)
    (day / "run-20260610.json").write_text("{}", encoding="utf-8")
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/snapshots")
    assert [ref["runId"] for ref in response.json()["snapshots"]] == ["run-20260610"]
