from __future__ import annotations

from wolves.config import Settings
from wolves.sim.format import load_format


def test_every_scheduled_city_has_a_venue_and_key_facts_hold():
    fmt = load_format(Settings().data_dir)
    venues = fmt.venue_by_city()

    scheduled = {m.city for m in fmt.group_matches} | {m.city for m in fmt.knockout}
    assert scheduled == set(venues)

    assert venues["Mexico City"].altitude_m == 2240
    roofed = {v.city for v in fmt.venues if v.roofed}
    assert roofed == {"Dallas", "Atlanta", "Los Angeles", "Vancouver", "Houston"}
    assert {v.country for v in fmt.venues} == {"USA", "MEX", "CAN"}
