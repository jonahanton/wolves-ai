from __future__ import annotations

import numpy as np

from wolves.sim.format import FormatData, Venue

HOST_COUNTRY = {"mexico": "MEX", "usa": "USA", "canada": "CAN"}
ALTITUDE_ACCLIMATISED = frozenset({"mexico", "ecuador", "colombia"})

CROWD_ELO = 65.0
TRAVEL_ELO = 25.0
ALTITUDE_ELO_PER_KM = 35.0
ALTITUDE_FLOOR_M = 1000.0


def team_venue_bonus(team_id: str, venue: Venue) -> float:
    """Rating bonus a team enjoys at a venue, decomposed as crowd + travel + altitude."""
    bonus = 0.0
    if HOST_COUNTRY.get(team_id) == venue.country:
        bonus += CROWD_ELO + TRAVEL_ELO
    excess_km = max(0.0, venue.altitude_m - ALTITUDE_FLOOR_M) / 1000.0
    if team_id in ALTITUDE_ACCLIMATISED:
        bonus += ALTITUDE_ELO_PER_KM * excess_km
    return bonus


def venue_bonus_table(fmt: FormatData) -> dict[str, np.ndarray]:
    """Per-city vector of rating bonuses aligned with fmt.teams."""
    return {
        v.city: np.array([team_venue_bonus(t.id, v) for t in fmt.teams], dtype=np.float64) for v in fmt.venues
    }
