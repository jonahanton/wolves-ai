"""Map market feed country names onto tournament team ids.

Feeds disagree with the FIFA register on a handful of names (USA stays USA,
but "South Korea" is Korea Republic, "Ivory Coast" is Côte d'Ivoire). Matching
is accent- and case-insensitive with an explicit alias table for the rest.
"""

from __future__ import annotations

import unicodedata
from typing import Protocol


class NamedTeam(Protocol):
    id: str
    name: str


_ALIASES = {
    "south korea": "korea-republic",
    "ivory coast": "cote-d-ivoire",
    "turkey": "turkiye",
    "iran": "ir-iran",
    "dr congo": "congo-dr",
    "democratic republic of the congo": "congo-dr",
    "cape verde": "cabo-verde",
    "czech republic": "czechia",
    "united states": "usa",
    "bosnia": "bosnia-and-herzegovina",
}


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _name_table(teams: list[NamedTeam]) -> dict[str, str]:
    table = {_normalise(t.name): t.id for t in teams}
    table.update(_ALIASES)
    return table


def team_id_for_name(name: str, teams: list[NamedTeam]) -> str | None:
    """Resolve an exact feed name to a team id, or None when unrecognised."""
    return _name_table(teams).get(_normalise(name))


def team_id_in_text(text: str, teams: list[NamedTeam]) -> str | None:
    """Find the team whose name (or alias) appears in free text such as a
    market question; longest names first so 'South Korea' beats partials."""
    haystack = _normalise(text)
    for name, team_id in sorted(_name_table(teams).items(), key=lambda kv: -len(kv[0])):
        if name in haystack:
            return team_id
    return None
