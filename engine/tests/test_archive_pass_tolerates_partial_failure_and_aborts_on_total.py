from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from wolves.archive import AllSourcesFailedError, archive_pass
from wolves.clients.odds.contracts import CreditUsage, RawOddsResponse
from wolves.config import Settings

NOW = datetime(2026, 6, 11, 14, 30, tzinfo=UTC)


class StubOdds:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def outrights_raw(self) -> RawOddsResponse:
        if self._fail:
            raise ConnectionError("odds api down")
        return RawOddsResponse(payload=[{"id": "evt", "bookmakers": []}], credits=CreditUsage(last_cost=2))

    async def h2h_raw(self) -> RawOddsResponse:
        if self._fail:
            raise ConnectionError("odds api down")
        return RawOddsResponse(payload=[], credits=CreditUsage(last_cost=0))


class StubPolymarket:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def winner_events(self) -> list[dict[str, Any]]:
        if self._fail:
            raise ConnectionError("gamma down")
        return [{"markets": [{"question": "Will England win?", "outcomePrices": '["0.1"]'}]}]


async def test_failed_source_is_recorded_without_losing_the_others(tmp_path):
    settings = Settings(runs_root=tmp_path, agent_state_bucket="")

    key = await archive_pass(settings, odds=StubOdds(fail=True), polymarket=StubPolymarket(), now=NOW)

    assert key == "2026-06-11/1430.json"
    written = json.loads((tmp_path / "odds-archive" / key).read_text(encoding="utf-8"))
    assert written["sources"]["odds_outrights"]["error"].startswith("ConnectionError")
    assert written["sources"]["odds_outrights"]["payload"] is None
    assert written["sources"]["polymarket"]["error"] is None
    assert written["sources"]["polymarket"]["payload"][0]["markets"][0]["outcomePrices"] == '["0.1"]'


async def test_all_sources_failing_aborts_and_writes_nothing(tmp_path):
    settings = Settings(runs_root=tmp_path, agent_state_bucket="")

    with pytest.raises(AllSourcesFailedError) as exc_info:
        await archive_pass(settings, odds=StubOdds(fail=True), polymarket=StubPolymarket(fail=True), now=NOW)

    assert set(exc_info.value.errors) == {"odds_outrights", "odds_h2h", "polymarket"}
    assert not (tmp_path / "odds-archive").exists()
