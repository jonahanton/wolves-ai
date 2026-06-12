from __future__ import annotations

from tests.fakes import FakeS3Client, build_test_app, client_for

SIDECAR_KEY = "snapshots/2026/06/12/agent-20260612-211712.pairing-matrices.json"
SIDECAR_BODY = '{"rounds": {"r32": {"england": [{"opponent": "senegal", "p": 0.41}]}}}'


async def test_valid_name_round_trips_the_stored_blob_verbatim():
    s3 = FakeS3Client({SIDECAR_KEY: SIDECAR_BODY})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/snapshots/agent-20260612-211712/sidecars/pairing-matrices")
    assert response.status_code == 200
    assert response.text == SIDECAR_BODY


async def test_unknown_dataset_name_is_400():
    async with client_for(build_test_app()) as client:
        response = await client.get("/snapshots/run-20260612/sidecars/nope")
    assert response.status_code == 400
    assert response.json() == {"error": "unknown sidecar dataset"}


async def test_invalid_run_id_is_400():
    async with client_for(build_test_app()) as client:
        response = await client.get("/snapshots/../etc/sidecars/bracket-samples")
    assert response.status_code in (400, 404)


async def test_missing_sidecar_is_404(tmp_path):
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/snapshots/run-20260612/sidecars/bracket-samples")
    assert response.status_code == 404
    assert response.json() == {"error": "sidecar not found"}


async def test_sidecar_keys_never_appear_in_the_snapshot_index():
    s3 = FakeS3Client({SIDECAR_KEY: SIDECAR_BODY, "snapshots/2026/06/12/run-20260612.json": "{}"})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/snapshots")
    assert [ref["runId"] for ref in response.json()["snapshots"]] == ["run-20260612"]
