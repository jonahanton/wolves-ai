from __future__ import annotations

import unicodedata

# Registry ids whose slugified martj42 name differs from the id itself.
_REGISTRY_ALIASES: dict[str, str] = {
    "czechia": "Czech Republic",
    "korea-republic": "South Korea",
    "turkiye": "Turkey",
    "usa": "United States",
    "cote-d-ivoire": "Ivory Coast",
    "ir-iran": "Iran",
    "cabo-verde": "Cape Verde",
    "congo-dr": "DR Congo",
}


class UnmappedTeamError(Exception):
    """A registry team has no matching team in the results backbone."""

    def __init__(self, app_team_id: str, expected_name: str) -> None:
        self.app_team_id = app_team_id
        self.expected_name = expected_name
        super().__init__(f"registry team {app_team_id!r} not found in results as {expected_name!r}")


def team_key(name: str) -> str:
    """Canonical dataset key for a source team name: lowercase, accent-stripped, hyphenated."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch if ch.isalnum() else " " for ch in ascii_name.lower())
    return "-".join(cleaned.split())


def registry_team_key(app_team_id: str) -> str:
    """Dataset key for a 2026 registry id, honouring naming aliases."""
    alias = _REGISTRY_ALIASES.get(app_team_id)
    return team_key(alias) if alias is not None else app_team_id


def expected_results_name(app_team_id: str) -> str:
    return _REGISTRY_ALIASES.get(app_team_id, app_team_id.replace("-", " "))
