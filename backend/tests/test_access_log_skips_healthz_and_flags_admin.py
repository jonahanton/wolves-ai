from __future__ import annotations

import json
import logging

import pytest

from tests.fakes import ADMIN_HEADERS, build_test_app, client_for

ACCESS_LOGGER = "wolves_backend.access"


@pytest.fixture
def access_lines(caplog):
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)

    def lines() -> list[dict]:
        return [json.loads(record.message) for record in caplog.records if record.name == ACCESS_LOGGER]

    return lines


async def test_healthz_is_not_logged(access_lines):
    async with client_for(build_test_app()) as client:
        await client.get("/healthz")
    assert access_lines() == []


async def test_request_line_carries_method_path_status_and_client(access_lines):
    async with client_for(build_test_app()) as client:
        await client.get("/runs", headers={"User-Agent": "pytest-agent"})
    (line,) = access_lines()
    assert line["method"] == "GET"
    assert line["path"] == "/runs"
    assert line["status"] == 200
    assert line["duration_ms"] >= 0
    assert line["user_agent"] == "pytest-agent"
    assert "client_ip" in line
    assert "admin" not in line


async def test_valid_admin_token_flags_the_line(access_lines):
    async with client_for(build_test_app(), headers=ADMIN_HEADERS) as client:
        await client.get("/admin/schedule")
    (line,) = access_lines()
    assert line["admin"] is True


async def test_wrong_token_is_not_flagged_admin(access_lines):
    async with client_for(build_test_app(), headers={"Authorization": "Bearer wrong"}) as client:
        await client.get("/admin/schedule")
    (line,) = access_lines()
    assert line["status"] == 403
    assert "admin" not in line
