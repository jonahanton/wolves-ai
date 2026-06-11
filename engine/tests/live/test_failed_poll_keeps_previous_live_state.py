from __future__ import annotations

from datetime import UTC, datetime

from wolves.config import Settings
from wolves.live_state import LiveState, LiveStateStore
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import LIVE_STATE


def _state() -> LiveState:
    return LiveState(
        generated_at="2026-06-11T19:30:00+00:00",
        fetched_at="2026-06-11T19:30:00+00:00",
        stale_after="2026-06-11T19:32:00+00:00",
        live_match_count=1,
        fixtures=[
            {
                "external_id": 1300001,
                "match": 1,
                "status": "live",
                "kickoff": "2026-06-11T19:00:00+00:00",
                "minute": 60,
                "home_id": "mexico",
                "away_id": "south_africa",
                "home_name": "Mexico",
                "away_name": "South Africa",
                "home_goals": 1,
                "away_goals": 0,
                "forecast": {"source": "in_match", "p_home": 0.78, "p_draw": 0.15, "p_away": 0.07},
            }
        ],
        title_probs={"mexico": 0.2},
    )


def test_failed_poll_keeps_previous_live_state(tmp_path) -> None:
    store = LiveStateStore(ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local")))
    state = _state()
    store.put(state)

    failed = store.record_failure(message="timeout", now=datetime(2026, 6, 11, 19, 33, tzinfo=UTC))

    assert failed.poll_status == "failed"
    assert failed.fixtures == state.fixtures
    assert failed.fetched_at == state.fetched_at
    assert failed.message == "timeout"


def test_failed_polls_write_no_history_points(tmp_path) -> None:
    artifacts = ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local"))
    store = LiveStateStore(artifacts)
    store.put(_state())
    points_after_ok = list((tmp_path / "live" / "history").rglob("*.json"))

    store.record_failure(message="timeout", now=datetime(2026, 6, 11, 19, 33, tzinfo=UTC))

    assert list((tmp_path / "live" / "history").rglob("*.json")) == points_after_ok
    assert store.load().poll_status == "failed"


def test_torn_state_file_degrades_to_a_fresh_failed_state(tmp_path) -> None:
    artifacts = ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local"))
    store = LiveStateStore(artifacts)
    path = tmp_path / LIVE_STATE.key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"generated_at": "2026-06-11T19:30', encoding="utf-8")

    failed = store.record_failure(message="timeout", now=datetime(2026, 6, 11, 19, 33, tzinfo=UTC))

    assert failed.poll_status == "failed"
    assert failed.fixtures == []
