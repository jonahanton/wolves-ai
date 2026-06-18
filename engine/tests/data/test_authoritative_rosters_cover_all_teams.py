from __future__ import annotations

import json

import pytest

from wolves.config import Settings
from wolves.data.sources.squad_rosters import load_rosters

RATINGS_DIR = Settings().data_dir / "ratings"


@pytest.fixture(scope="module")
def rosters():
    return load_rosters(RATINGS_DIR)


def test_every_registry_team_has_an_authoritative_roster(rosters) -> None:
    registry = {entry["id"] for entry in json.loads((Settings().data_dir / "format" / "teams.json").read_text())}
    assert set(rosters) == registry


def test_each_roster_is_a_plausible_unique_squad(rosters) -> None:
    for team, players in rosters.items():
        assert 23 <= len(players) <= 27, (team, len(players))
        assert len(set(players)) == len(players), team
