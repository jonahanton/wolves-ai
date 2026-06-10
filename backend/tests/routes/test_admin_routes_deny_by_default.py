from __future__ import annotations

import pytest

from tests.fakes import build_test_app, client_for

ADMIN_CALLS = [
    ("GET", "/admin/run-history"),
    ("GET", "/admin/schedule"),
    ("POST", "/admin/schedule"),
    ("POST", "/admin/run-now"),
    ("POST", "/admin/stop"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
async def test_denied_without_bypass(method, path):
    async with client_for(build_test_app()) as client:
        response = await client.request(method, path)
    assert response.status_code == 403
    assert response.json() == {"error": "forbidden"}


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
async def test_bypass_never_honoured_in_production(method, path):
    async with client_for(build_test_app(environment="production", admin_dev_bypass=True)) as client:
        response = await client.request(method, path)
    assert response.status_code == 403


async def test_bypass_admits_locally():
    async with client_for(build_test_app(admin_dev_bypass=True)) as client:
        response = await client.get("/admin/schedule")
    assert response.status_code == 200
