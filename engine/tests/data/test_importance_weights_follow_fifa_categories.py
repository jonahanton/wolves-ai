from __future__ import annotations

import pytest

from wolves.data.importance import importance_weight


@pytest.mark.parametrize(
    ("tournament", "weight"),
    [
        ("FIFA World Cup", 4.0),
        ("FIFA World Cup qualification", 2.5),
        ("UEFA Euro", 3.0),
        ("UEFA Euro qualification", 2.5),
        ("Copa América", 3.0),
        ("African Cup of Nations qualification", 2.5),
        ("UEFA Nations League", 2.5),
        ("CONCACAF Nations League qualification", 2.5),
        ("FIFA Confederations Cup", 3.0),
        ("Friendly", 1.0),
        ("King's Cup", 1.0),
    ],
)
def test_weight_for_tournament_label(tournament: str, weight: float) -> None:
    assert importance_weight(tournament) == weight
