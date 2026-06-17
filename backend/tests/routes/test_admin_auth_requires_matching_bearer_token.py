from __future__ import annotations

import pytest

from tests.fakes import ADMIN_HEADERS, build_test_app, client_for

ADMIN_CALLS = [
    ("GET", "/admin/schedule"),
    ("POST", "/admin/schedule"),
    ("GET", "/admin/runs/active"),
    ("POST", "/admin/run-now"),
    ("POST", "/admin/stop"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
async def test_missing_token_is_unauthorised(method, path):
    async with client_for(build_test_app()) as client:
        response = await client.request(method, path)
    assert response.status_code == 401
    assert response.json() == {"error": "authentication required"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
async def test_wrong_token_is_forbidden(method, path):
    async with client_for(build_test_app(), headers={"Authorization": "Bearer wrong-token"}) as client:
        response = await client.request(method, path)
    assert response.status_code == 403


async def test_correct_token_admits():
    async with client_for(build_test_app(), headers=ADMIN_HEADERS) as client:
        response = await client.get("/admin/schedule")
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("headers", "status"),
    [(None, 401), (ADMIN_HEADERS, 403), ({"Authorization": "Bearer "}, 401)],
)
async def test_unset_token_denies_everything(headers, status):
    async with client_for(build_test_app(admin_token=""), headers=headers) as client:
        response = await client.get("/admin/schedule")
    assert response.status_code == status
