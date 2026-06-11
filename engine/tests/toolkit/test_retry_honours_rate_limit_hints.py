from __future__ import annotations

import datetime as dt

import httpx
import pytest

from wolves.toolkit import _retry
from wolves.toolkit._retry import (
    _parse_rate_limit_reset,
    _parse_retry_after,
    request_with_retry,
)


def test_retry_after_numeric_seconds():
    assert _parse_retry_after("7") == 7.0
    assert _parse_retry_after(" 2.5 ") == 2.5
    assert _parse_retry_after("-3") == 0.0


def test_retry_after_http_date():
    future = dt.datetime.now(tz=dt.UTC) + dt.timedelta(seconds=30)
    parsed = _parse_retry_after(future.strftime("%a, %d %b %Y %H:%M:%S GMT"))
    assert parsed is not None and 0 < parsed <= 31

    past = dt.datetime.now(tz=dt.UTC) - dt.timedelta(seconds=30)
    assert _parse_retry_after(past.strftime("%a, %d %b %Y %H:%M:%S GMT")) == 0.0


def test_retry_after_garbage_is_none():
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("soonish") is None


def test_rate_limit_reset_delta_vs_epoch():
    assert _parse_rate_limit_reset("12") == 12.0
    epoch = dt.datetime.now(tz=dt.UTC).timestamp() + 45
    parsed = _parse_rate_limit_reset(str(epoch))
    assert parsed is not None and 40 < parsed <= 46


async def test_429_retries_honouring_retry_after(monkeypatch):
    sleeps: list[float] = []

    async def _record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(_retry.asyncio, "sleep", _record_sleep)

    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(429, headers={"Retry-After": "4"})
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await request_with_retry(client, "GET", "https://api.example/x")

    assert response.status_code == 200
    assert calls == 3
    assert sleeps == [4.0, 4.0]


async def test_exhausted_retries_raise_last_error(monkeypatch):
    async def _no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(_retry.asyncio, "sleep", _no_sleep)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await request_with_retry(client, "GET", "https://api.example/x", max_retries=2)


async def test_4xx_other_than_429_returned_without_retry():
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await request_with_retry(client, "GET", "https://api.example/x")

    assert response.status_code == 404
    assert calls == 1
