from __future__ import annotations

from wolves.config import Settings
from wolves.gate.registry import ELO_CHAMPION_ID, ChampionRecord, ChampionRegistry


def test_missing_record_yields_the_elo_baseline(tmp_path) -> None:
    registry = ChampionRegistry(Settings(runs_root=tmp_path, agent_state_bucket=""))
    assert registry.load().model_id == ELO_CHAMPION_ID


def test_promote_then_load_round_trips(tmp_path) -> None:
    registry = ChampionRegistry(Settings(runs_root=tmp_path, agent_state_bucket=""))
    record = ChampionRecord(
        model_id="poisson-decay",
        model_version="abc123",
        dataset_id="v1",
        half_life_days=913.0,
        blend_weight=0.24,
        promoted_at="2026-06-10T12:00:00+00:00",
        rationale="test",
    )

    registry.promote(record)
    loaded = registry.load()

    assert loaded == record
