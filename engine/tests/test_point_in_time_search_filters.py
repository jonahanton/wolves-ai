from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx

from wolves.connectors._dates import freshness_range, parse_date, to_iso8601
from wolves.connectors.brave import BraveClient
from wolves.connectors.exa import ExaClient


def test_parse_date_returns_aware_utc():
    parsed = parse_date("2026-06-01T12:00:00+02:00")
    assert parsed == datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    assert parse_date("2026-06-01").tzinfo is UTC
    assert parse_date("garbage") is None
    assert parse_date(None) is None


def test_freshness_range_ends_at_as_of_date():
    window = freshness_range("2026-06-01")
    assert window is not None
    start, _, end = window.partition("to")
    assert end == "2026-06-01"
    assert start == (datetime(2026, 6, 1, tzinfo=UTC) - timedelta(days=3650)).date().isoformat()


def test_to_iso8601_emits_full_instant():
    assert to_iso8601("2026-06-01") == "2026-06-01T00:00:00.000Z"
    assert to_iso8601("nonsense") is None


async def test_brave_bounds_results_at_as_of_date():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"web": {"results": []}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    brave = BraveClient("key", client=client)
    await brave.search("query", end_published_date="2026-06-01")
    await client.aclose()

    params = dict(captured[0].url.params)
    assert params["freshness"].endswith("to2026-06-01")


async def test_exa_bounds_results_with_end_published_date():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    exa = ExaClient("key", client=client)
    await exa.search("query", end_published_date="2026-06-01")
    await client.aclose()

    body = json.loads(captured[0].content)
    assert body["endPublishedDate"] == "2026-06-01T00:00:00.000Z"
