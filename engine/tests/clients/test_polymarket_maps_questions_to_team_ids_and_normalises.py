from __future__ import annotations

import pytest

from wolves.clients.odds import FakePolymarketClient, GammaPolymarketClient, winner_probabilities
from wolves.config import get_settings
from wolves.sim.format import load_format


@pytest.fixture(scope="module")
def teams():
    return load_format(get_settings().data_dir).teams


async def test_fixture_parses_sixty_markets_with_yes_price_first():
    markets = await FakePolymarketClient().winner_markets()
    assert len(markets) == 60
    france = next(m for m in markets if "France" in m.question)
    assert france.yes_price == pytest.approx(0.162)


@pytest.mark.parametrize(
    ("feed_name", "team_id"),
    [
        ("USA", "usa"),
        ("South Korea", "korea-republic"),
        ("Ivory Coast", "cote-d-ivoire"),
        ("Turkey", "turkiye"),
        ("Iran", "ir-iran"),
        ("Cape Verde", "cabo-verde"),
        ("Czech Republic", "czechia"),
        ("DR Congo", "congo-dr"),
        ("Curacao", "curacao"),
    ],
)
async def test_feed_names_map_to_register_team_ids(teams, feed_name, team_id):
    markets = await FakePolymarketClient().winner_markets()
    probs = winner_probabilities(markets, teams)
    question = next(m for m in markets if feed_name in m.question)
    assert question is not None
    assert team_id in probs


async def test_probabilities_normalise_to_one_over_mapped_teams_only(teams):
    markets = await FakePolymarketClient().winner_markets()
    probs = winner_probabilities(markets, teams)
    team_ids = {t.id for t in teams}
    assert set(probs) <= team_ids
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-9)
    assert probs["france"] > probs["spain"] > probs["england"] > probs["portugal"]


@pytest.mark.smoke
async def test_live_winner_markets_smoke():
    client = GammaPolymarketClient()
    markets = await client.winner_markets()
    await client.aclose()
    assert markets
    assert all(0.0 <= m.yes_price <= 1.0 for m in markets)
