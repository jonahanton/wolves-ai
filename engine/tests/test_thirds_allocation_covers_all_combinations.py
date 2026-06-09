from __future__ import annotations

from itertools import combinations

from wolves.config import Settings
from wolves.sim.format import GROUPS, load_format
from wolves.sim.mc import allocate_thirds


def _slot_elig():
    fmt = load_format(Settings().data_dir)
    return [
        (m.match, [GROUPS.index(g) for g in m.away.removeprefix("3:")]) for m in fmt.knockout if m.away.startswith("3:")
    ]


def test_every_combination_of_eight_thirds_is_allocatable():
    slot_elig = _slot_elig()
    for combo in combinations(range(12), 8):
        assert allocate_thirds(frozenset(combo), slot_elig) is not None, combo


def test_third_of_group_l_only_ever_lands_in_match_87():
    slot_elig = _slot_elig()
    group_l = GROUPS.index("L")
    eligible_matches = {match for match, elig in slot_elig if group_l in elig}
    assert eligible_matches == {87}
    for combo in combinations(range(12), 8):
        if group_l not in combo:
            continue
        assignment = allocate_thirds(frozenset(combo), slot_elig)
        assert assignment is not None
        assert assignment[87] == group_l
