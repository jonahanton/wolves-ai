from __future__ import annotations

from tests.fakes import FakeS3Client, build_test_app, client_for

ARCHIVE = {
    "odds-archive/2026-06-09/110000.json": '{"raw": true}',
    "odds-archive/2026-06-09/110000.series.json": '{"t": "110000"}',
    "odds-archive/2026-06-10/090000.series.json": '{"t": "090000"}',
    "odds-archive/2026-06-10/100000.series.json": '{"t": "100000"}',
    "odds-archive/closes/wc2022/close.json": "{}",
}


async def test_dates_lists_archive_days_excluding_closes():
    async with client_for(build_test_app(s3=FakeS3Client(ARCHIVE))) as client:
        response = await client.get("/odds/dates")
    assert response.json() == {"dates": ["2026-06-09", "2026-06-10"]}


async def test_day_assembles_series_points_in_time_order_ignoring_raw_payloads():
    async with client_for(build_test_app(s3=FakeS3Client(ARCHIVE))) as client:
        response = await client.get("/odds/2026-06-10")
    assert response.json() == {"date": "2026-06-10", "points": [{"t": "090000"}, {"t": "100000"}]}


async def test_day_without_series_points_is_404():
    async with client_for(build_test_app(s3=FakeS3Client(ARCHIVE))) as client:
        response = await client.get("/odds/2026-06-11")
    assert response.status_code == 404


async def test_malformed_date_is_400():
    async with client_for(build_test_app(s3=FakeS3Client(ARCHIVE))) as client:
        response = await client.get("/odds/not-a-date")
    assert response.status_code == 400
