from __future__ import annotations

from types import SimpleNamespace

from wolves.quant.wolves_quant import _spread
from wolves.sim.spread import SpreadResult, SpreadRow


def test_mixture_spread_frame_is_indexed_by_team_and_has_team_column(monkeypatch, tmp_path):
    _spread._CACHE.clear()
    monkeypatch.setattr(_spread, "_resolve_worlds", lambda *_args: {"base": (1.0, [])})
    monkeypatch.setattr(
        _spread,
        "context",
        lambda: SimpleNamespace(focus_team="england", as_of="2026-06-15", runs_root=tmp_path),
    )
    monkeypatch.setattr(_spread, "forecaster", lambda: object())
    monkeypatch.setattr(_spread, "yesterday_bands", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        _spread,
        "mixture_spread_rows",
        lambda *_args, **_kwargs: SpreadResult(
            rows=[
                SpreadRow(
                    team="england",
                    mean=0.12,
                    p10=0.09,
                    p90=0.15,
                    width_pp=6.0,
                    floor_p10=0.1,
                    floor_p90=0.14,
                    floor_width_pp=4.0,
                    vs_floor=1.5,
                    yesterday_p10=None,
                    yesterday_p90=None,
                    world_means={"base": 0.12},
                )
            ],
            provenance="parameters_only",
            n_worlds=1,
            n_sims_per_world=20_000,
            parameter_draws=200,
            note="england band 6.0pp is 1.5x the parameter floor",
        ),
    )

    frame = _spread.mixture_spread(scenarios=[])["teams"]

    assert list(frame.index) == ["england"]
    assert frame.loc["england", "team"] == "england"
