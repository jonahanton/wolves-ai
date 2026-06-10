from __future__ import annotations

# FIFA-style importance weights for the time-decayed fit: friendly 1,
# qualifiers and Nations Leagues 2.5, confederation finals 3, World Cup 4.
WORLD_CUP_WEIGHT = 4.0
CONFEDERATION_WEIGHT = 3.0
QUALIFIER_WEIGHT = 2.5
FRIENDLY_WEIGHT = 1.0

_CONFEDERATION_FINALS = (
    "UEFA Euro",
    "Copa América",
    "African Cup of Nations",
    "Africa Cup of Nations",
    "AFC Asian Cup",
    "CONCACAF Championship",
    "Gold Cup",
    "Oceania Nations Cup",
    "OFC Nations Cup",
    "FIFA Confederations Cup",
)


def importance_weight(tournament: str) -> float:
    """Weight for a martj42 tournament label."""
    if "qualification" in tournament:
        return QUALIFIER_WEIGHT
    if tournament == "FIFA World Cup":
        return WORLD_CUP_WEIGHT
    if "Nations League" in tournament:
        return QUALIFIER_WEIGHT
    if any(tournament.startswith(finals) for finals in _CONFEDERATION_FINALS):
        return CONFEDERATION_WEIGHT
    return FRIENDLY_WEIGHT
