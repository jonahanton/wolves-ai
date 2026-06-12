from __future__ import annotations

import json
from collections import Counter

import pytest

from wolves.config import Settings
from wolves.data.sources.squad_players import load_squad_players, team_totals

RATINGS_DIR = Settings().data_dir / "ratings"


@pytest.fixture(scope="module")
def players():
    return load_squad_players(RATINGS_DIR)


def test_squad_values_file_is_the_exact_aggregation_of_the_latest_players_file(players) -> None:
    on_disk = json.loads((RATINGS_DIR / "squad-values.json").read_text(encoding="utf-8"))["valuesEurM"]
    assert on_disk == team_totals(players)


def test_all_48_registry_teams_carry_a_plausible_squad(players) -> None:
    registry = {entry["id"] for entry in json.loads((Settings().data_dir / "format" / "teams.json").read_text())}
    sizes = Counter(record.app_team_id for record in players)
    assert set(sizes) == registry
    assert all(23 <= size <= 30 for size in sizes.values()), sizes
