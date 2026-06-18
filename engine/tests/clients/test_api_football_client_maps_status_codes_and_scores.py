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
    live_item = next(i for i in body["response"] if i["fixture"]["id"] == 1300015)
    enriched = json.loads(json.dumps(live_item))
    enriched["events"] = [
        {"type": "Card", "detail": "Yellow Card", "team": {"id": 9}},
        {"type": "Card", "detail": "Red Card", "team": {"id": 1001}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-apisports-key"] == "test-key"
        if "ids" in request.url.params:
            assert request.url.params["ids"] == "1300015"
            return httpx.Response(200, json={"errors": [], "response": [enriched]})
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
    assert (by_id[1300015].home_reds, by_id[1300015].away_reds) == (0, 1)
    assert by_id[1300021].status == "scheduled"
    assert by_id[1300021].home_goals is None
    assert by_id[1300030].status == "abandoned"


async def test_live_statistics_parse_into_shots_and_possession():
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    live_item = next(i for i in body["response"] if i["fixture"]["id"] == 1300015)
    enriched = json.loads(json.dumps(live_item))
    enriched["statistics"] = [
        {
            "team": {"id": 9},
            "statistics": [
                {"type": "Shots on Goal", "value": 6},
                {"type": "Total Shots", "value": 13},
                {"type": "Ball Possession", "value": "61%"},
            ],
        },
        {
            "team": {"id": 1001},
            "statistics": [
                {"type": "Shots on Goal", "value": 2},
                {"type": "Total Shots", "value": 5},
                {"type": "Ball Possession", "value": "39%"},
            ],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if "ids" in request.url.params:
            return httpx.Response(200, json={"errors": [], "response": [enriched]})
        return httpx.Response(200, json=body)

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    matches = await client.fixtures()
    await client.aclose()

    live = next(m for m in matches if m.fixture_id == 1300015)
    assert (live.home_shots_on, live.away_shots_on) == (6, 2)
    assert (live.home_total_shots, live.away_total_shots) == (13, 5)
    assert live.home_possession == pytest.approx(0.61)
    assert live.away_possession == pytest.approx(0.39)


async def test_fixtures_without_a_statistics_block_leave_signals_unset():
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    scheduled = next(m for m in await _client_from(body).fixtures() if m.fixture_id == 1300021)
    assert scheduled.home_shots_on is None
    assert scheduled.home_possession is None


def _client_from(body: dict) -> ApiFootballClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize(
    ("short", "status", "period"),
    [
        ("AWD", "finished", "regulation"),
        ("WO", "finished", "regulation"),
        ("SUSP", "live", "regulation"),
        ("INT", "live", "regulation"),
        ("PST", "scheduled", "regulation"),
        ("ET", "live", "extra_time"),
        ("BT", "live", "extra_time"),
        ("P", "live", "shootout"),
    ],
)
async def test_operational_statuses_map_to_forecastable_states(short: str, status: str, period: str):
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    item = next(i for i in body["response"] if i["fixture"]["id"] == 1300001)
    item["fixture"]["status"] = {"short": short, "elapsed": 100}
    payload = {"errors": [], "response": [item]}

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    fixture = (await client.fixtures())[0]
    await client.aclose()
    assert (fixture.status, fixture.period) == (status, period)


async def test_season_payload_pagination_is_followed():
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    finished = [i for i in body["response"] if i["fixture"]["status"]["short"] == "FT"]
    pages = {
        1: {"errors": [], "response": finished[:1], "paging": {"current": 1, "total": 2}},
        2: {"errors": [], "response": finished[1:], "paging": {"current": 2, "total": 2}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[int(request.url.params.get("page", "1"))])

    client = ApiFootballClient("test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    matches = await client.fixtures()
    await client.aclose()
    assert [m.fixture_id for m in matches] == [1300001, 1300002]


async def test_fake_filters_by_date():
    fake = FakeFixturesClient()
    matches = await fake.fixtures(date="2026-06-11")
    assert [m.home for m in matches] == ["Mexico"]


@pytest.mark.parametrize(
    "payload",
    [
        {"errors": {"token": "bad key"}, "response": []},
        {"errors": [], "response": []},
    ],
)
async def test_error_and_empty_payloads_are_not_successful_polls(payload: dict):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

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
