from __future__ import annotations

import pytest

from tests.fakes import build_test_app, client_for

FRONTEND_KEY = "test-frontend-key"
KEY_HEADERS = {"X-Wolves-Key": FRONTEND_KEY}


async def test_missing_key_is_unauthorised():
    async with client_for(build_test_app(frontend_key=FRONTEND_KEY)) as client:
        response = await client.get("/runs")
    assert response.status_code == 401
    assert response.json() == {"error": "authentication required"}
    assert response.headers["www-authenticate"] == "X-Wolves-Key"


async def test_wrong_key_is_unauthorised():
    async with client_for(build_test_app(frontend_key=FRONTEND_KEY), headers={"X-Wolves-Key": "nope"}) as client:
        response = await client.get("/runs")
    assert response.status_code == 401


async def test_correct_key_admits():
    async with client_for(build_test_app(frontend_key=FRONTEND_KEY), headers=KEY_HEADERS) as client:
        response = await client.get("/runs")
    assert response.status_code == 200


@pytest.mark.parametrize("headers", [None, {"X-Wolves-Key": "nope"}])
async def test_healthz_is_exempt(headers):
    async with client_for(build_test_app(frontend_key=FRONTEND_KEY), headers=headers) as client:
        response = await client.get("/healthz")
    assert response.status_code == 200


async def test_unset_key_leaves_gate_open():
    async with client_for(build_test_app()) as client:
        response = await client.get("/runs")
    assert response.status_code == 200


async def test_openapi_schema_is_hidden_outside_local():
    async with client_for(build_test_app(environment="production", frontend_key=FRONTEND_KEY)) as client:
        response = await client.get("/openapi.json", headers=KEY_HEADERS)
    assert response.status_code == 404
