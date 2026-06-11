from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.agent.forecast_artifact import worlds_from_payload
from wolves.agent.market_base import seed_baseline_payload
from wolves.config import Settings
from wolves.forecast import Forecaster, StrengthPerturbation


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    instance = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    # Test seam: bypasses fit() so no dataset is needed.
    instance._state = synthetic_state()
    return instance


def _archive(tmp_path: Path, market: dict[str, float]) -> Path:
    archive = tmp_path / "odds-archive" / "2026-06-11"
    archive.mkdir(parents=True)
    point = {
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "outright_bookmakers": market,
        "outright_polymarket": {},
        "matches": [],
    }
    (archive / "120000.series.json").write_text(json.dumps(point), encoding="utf-8")
    return tmp_path / "odds-archive"


def test_priced_archive_seeds_model_and_market_worlds(forecaster: Forecaster, tmp_path: Path):
    base = forecaster.title_probs(n_sims=2_000, seed=0)
    favourite = max(base, key=base.get)
    archive = _archive(tmp_path, {favourite: min(0.9, base[favourite] + 0.10)})

    payload, summary = seed_baseline_payload(forecaster, archive)

    weight = forecaster.champion.blend_weight or 0.27
    assert payload["weights"] == {"model_base": round(weight, 4), "market_base": round(1 - weight, 4)}
    [pert] = payload["worlds"]["market_base"]["perturbations"]
    canonical = StrengthPerturbation(team=favourite, delta=0.1, reason="key probe").team
    assert pert["team"] == canonical and pert["delta"] > 0
    assert "Two-base" in summary
    worlds_from_payload(payload)


def test_empty_archive_degrades_to_the_single_world_baseline(forecaster: Forecaster, tmp_path: Path):
    payload, summary = seed_baseline_payload(forecaster, tmp_path / "odds-archive")
    assert payload["weights"] == {"baseline": 1.0}
    assert "single-world" in summary
