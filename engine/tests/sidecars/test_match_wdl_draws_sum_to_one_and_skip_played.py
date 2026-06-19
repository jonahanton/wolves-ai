from __future__ import annotations

from tests.sidecars.conftest import PLAYED_MATCH, WDL_CURVE_DRAWS
from wolves.sidecars import build_match_wdl_draws


def test_per_draw_triples_sum_to_one_and_played_matches_are_absent(inputs):
    payload = build_match_wdl_draws(inputs)
    expected = {m.match for m in inputs.fmt.group_matches} - {PLAYED_MATCH}
    assert set(payload.matches) == expected
    for wdl in payload.matches.values():
        assert len(wdl.p_home) == len(wdl.p_draw) == len(wdl.p_away) == WDL_CURVE_DRAWS
        for h, d, a in zip(wdl.p_home, wdl.p_draw, wdl.p_away, strict=True):
            # 4 dp rounding on three weighted components.
            assert abs(h + d + a - 1.0) < 2e-3
