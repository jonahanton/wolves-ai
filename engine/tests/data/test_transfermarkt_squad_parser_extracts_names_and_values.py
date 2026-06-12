from __future__ import annotations

from pathlib import Path

import pytest

from wolves.data.sources.transfermarkt import SquadPageParseError, parse_squad_page, parse_value_eur_m

FIXTURE = Path(__file__).parent / "fixtures" / "transfermarkt_squad_page.html"


def test_squad_rows_parse_to_typed_players_with_nullable_value_and_shirt() -> None:
    players = parse_squad_page(FIXTURE.read_text(encoding="utf-8"), team_id="england")

    assert [(p.name, p.transfermarkt_id) for p in players] == [
        ("Dean Henderson", 258919),
        ("Marc Guéhi", 392757),
        ("Reece James", 472423),
    ]
    assert [(p.position, p.position_group) for p in players] == [
        ("Goalkeeper", "GK"),
        ("Centre-Back", "DF"),
        ("Right-Back", "DF"),
    ]
    assert [p.shirt_number for p in players] == [13, 6, None]
    assert [p.value_eur_m for p in players] == [28.0, 0.95, None]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("€180.00m", 180.0), ("€950k", 0.95), ("€1.20bn", 1200.0), ("-", None)],
)
def test_value_strings_convert_to_eur_millions(text: str, expected: float | None) -> None:
    assert parse_value_eur_m(text) == expected


def test_pages_without_squad_rows_fail_loudly_naming_the_team() -> None:
    with pytest.raises(SquadPageParseError) as excinfo:
        parse_squad_page("<html><body>maintenance</body></html>", team_id="qatar")
    assert excinfo.value.team_id == "qatar"
