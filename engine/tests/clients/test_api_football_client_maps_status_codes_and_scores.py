from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from wolves.clients.api_football import ApiFootballClient, FakeFixturesClient
from wolves.clients.api_football.client import ApiFootballPayloadError

_FIXTURE = Path(__file__).resolve().parents[2] / "wolves/clients/api_football/fixtures/fixtures.json"


async def test_fixture_parses_into_typed_matches_with_status_mapping():
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    body["response"][0]["teams"]["home"]["winner"] = True

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-apisports-key"] == "test-key"
        assert request.url.params["league"] == "1"
        return httpx.Response(200, json=body)

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    matches = await client.fixtures()
    await client.aclose()

    by_id = {m.fixture_id: m for m in matches}
    assert by_id[1300001].status == "finished"
    assert (by_id[1300001].home_goals, by_id[1300001].away_goals) == (2, 0)
    assert by_id[1300001].winner == "home"
    assert by_id[1300015].status == "live"
    assert by_id[1300015].elapsed == 63
    assert by_id[1300015].winner is None
    assert by_id[1300021].status == "scheduled"
    assert by_id[1300021].home_goals is None
    assert by_id[1300030].status == "abandoned"


async def test_fake_filters_by_date():
    fake = FakeFixturesClient()
    matches = await fake.fixtures(date="2026-06-11")
    assert [m.home for m in matches] == ["Mexico"]


async def test_fixture_api_errors_are_not_treated_as_empty_success():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": {"token": "bad key"}, "response": []})

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiFootballPayloadError):
        await client.fixtures()
    await client.aclose()


async def test_empty_tournament_fixture_payload_is_not_a_successful_live_poll():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [], "response": []})

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiFootballPayloadError):
        await client.fixtures()
    await client.aclose()


@pytest.mark.smoke
async def test_live_fixtures_smoke():
    from wolves.config import get_settings

    settings = get_settings()
    if not settings.api_football_key:
        pytest.skip("API_FOOTBALL_KEY not set")
    client = ApiFootballClient(settings.api_football_key)
    matches = await client.fixtures()
    await client.aclose()
    assert isinstance(matches, list)
