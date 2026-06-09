from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from wolves.clients.odds import FakeOddsClient, TheOddsApiClient, event_consensus

_FIXTURES = Path("wolves/clients/odds/fixtures")


def _transport() -> httpx.MockTransport:
    body = json.loads((_FIXTURES / "outrights.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apiKey"] == "test-key"
        return httpx.Response(
            200,
            json=body,
            headers={
                "x-requests-used": "37",
                "x-requests-remaining": "463",
                "x-requests-last": "1",
            },
        )

    return httpx.MockTransport(handler)


async def test_outrights_parse_into_typed_events_with_credit_usage():
    client = TheOddsApiClient("test-key", client=httpx.AsyncClient(transport=_transport()))
    response = await client.outrights()
    await client.aclose()

    assert response.credits.used == 37
    assert response.credits.remaining == 463
    assert response.credits.last_cost == 1
    event = response.events[0]
    assert len(event.bookmakers) == 3
    names = {o.name for o in event.bookmakers[0].markets[0].outcomes}
    assert {"Spain", "England", "Croatia"} <= names


async def test_fixture_consensus_is_a_coherent_outright_book():
    response = await FakeOddsClient().outrights()
    consensus = event_consensus(response.events[0], market_key="outrights")
    assert sum(consensus.values()) == pytest.approx(1.0, abs=1e-9)
    assert consensus["Spain"] > consensus["England"] > consensus["Croatia"]
    assert 0.10 < consensus["England"] < 0.20


@pytest.mark.smoke
async def test_live_outrights_smoke():
    from wolves.config import get_settings

    settings = get_settings()
    if not settings.odds_api_key:
        pytest.skip("ODDS_API_KEY not set")
    client = TheOddsApiClient(settings.odds_api_key)
    response = await client.outrights()
    await client.aclose()
    assert response.events
    assert response.credits.remaining is not None
