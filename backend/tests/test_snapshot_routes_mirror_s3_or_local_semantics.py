from __future__ import annotations

from tests.fakes import FakeS3Client, build_test_app, client_for


async def test_latest_served_from_local_runs_dir(tmp_path):
    (tmp_path / "latest.json").write_text('{"run": "local"}', encoding="utf-8")
    async with client_for(build_test_app(snapshot_dir=tmp_path)) as client:
        response = await client.get("/snapshots/latest")
    assert response.status_code == 200
    assert response.json() == {"run": "local"}


async def test_latest_missing_locally_is_404(tmp_path):
    async with client_for(build_test_app(snapshot_dir=tmp_path)) as client:
        response = await client.get("/snapshots/latest")
    assert response.status_code == 404
    assert response.json() == {"error": "no snapshot available"}


async def test_by_id_reads_dated_s3_key(tmp_path):
    s3 = FakeS3Client({"snapshots/2026/06/10/run-20260610.json": '{"run": "s3"}'})
    async with client_for(build_test_app(s3=s3)) as client:
        response = await client.get("/snapshots/run-20260610")
    assert response.status_code == 200
    assert response.json() == {"run": "s3"}


async def test_configured_bucket_wins_over_local_files(tmp_path):
    (tmp_path / "latest.json").write_text('{"run": "local"}', encoding="utf-8")
    async with client_for(build_test_app(snapshot_dir=tmp_path, s3=FakeS3Client())) as client:
        response = await client.get("/snapshots/latest")
    assert response.status_code == 404


async def test_invalid_run_id_is_400():
    async with client_for(build_test_app()) as client:
        response = await client.get("/snapshots/not-a-run-id")
    assert response.status_code == 400
    assert response.json() == {"error": "invalid run id"}


async def test_missing_run_id_is_404(tmp_path):
    async with client_for(build_test_app(snapshot_dir=tmp_path)) as client:
        response = await client.get("/snapshots/run-20260101")
    assert response.status_code == 404
    assert response.json() == {"error": "snapshot not found"}
