from __future__ import annotations

import pytest

from wolves.data.teams import registry_team_key, team_key


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Curaçao", "curacao"),
        ("Bosnia and Herzegovina", "bosnia-and-herzegovina"),
        ("Türkiye", "turkiye"),
        ("St. Kitts and Nevis", "st-kitts-and-nevis"),
    ],
)
def test_source_names_slug_to_keys(name: str, key: str) -> None:
    assert team_key(name) == key


@pytest.mark.parametrize(
    ("app_team_id", "key"),
    [
        ("czechia", "czech-republic"),
        ("korea-republic", "south-korea"),
        ("turkiye", "turkey"),
        ("usa", "united-states"),
        ("cote-d-ivoire", "ivory-coast"),
        ("ir-iran", "iran"),
        ("cabo-verde", "cape-verde"),
        ("congo-dr", "dr-congo"),
        ("england", "england"),
    ],
)
def test_registry_ids_resolve_to_results_keys(app_team_id: str, key: str) -> None:
    assert registry_team_key(app_team_id) == key
