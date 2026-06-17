from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from wolves.config import Settings
from wolves.run_agent import _live_attempt_blocker, _live_attempt_summary


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", **overrides)


def _write_events(tmp_path, run_id: str, events: list[dict], *, modified: datetime | None = None) -> None:
    path = tmp_path / "runs" / run_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    if modified is not None:
        stamp = modified.timestamp()
        path.touch()
        path.parent.touch()
        import os

        os.utime(path, (stamp, stamp))


def _attempt(as_of: str, status: str) -> dict:
    return {"kind": "live_attempt", "payload": {"as_of": as_of, "status": status}}


def _cost(micros: int) -> dict:
    return {"kind": "llm_call", "payload": {"cost_micros": micros}}


def test_live_attempt_guard_blocks_after_failed_attempt_limit(tmp_path):
    settings = _settings(tmp_path, agent_live_failed_attempt_limit=2)
    _write_events(tmp_path, "agent-1", [_attempt("2026-06-14", "failed")])
    _write_events(tmp_path, "agent-2", [_attempt("2026-06-14", "cancelled")])

    blocker = _live_attempt_blocker(settings, as_of="2026-06-14", ceiling_usd=5)

    assert blocker is not None
    assert "failed live attempt" in blocker


def test_live_attempt_guard_blocks_active_attempt(tmp_path):
    settings = _settings(tmp_path)
    _write_events(tmp_path, "agent-1", [_attempt("2026-06-14", "started")])

    blocker = _live_attempt_blocker(settings, as_of="2026-06-14", ceiling_usd=5)

    assert blocker is not None
    assert "already active" in blocker


def test_live_attempt_guard_treats_stale_started_attempt_as_failed(tmp_path):
    now = datetime(2026, 6, 15, tzinfo=UTC)
    settings = _settings(tmp_path, agent_live_active_ttl_minutes=60)
    _write_events(tmp_path, "agent-1", [_attempt("2026-06-14", "started")], modified=now - timedelta(hours=2))

    summary = _live_attempt_summary(settings, as_of="2026-06-14", now=now)

    assert summary.failed_attempts == 1
    assert summary.active_run_ids == ()


def test_live_attempt_guard_blocks_settled_spend_at_ceiling(tmp_path):
    settings = _settings(tmp_path)
    _write_events(tmp_path, "agent-1", [_cost(2_100_000), _attempt("2026-06-14", "complete")])

    blocker = _live_attempt_blocker(settings, as_of="2026-06-14", ceiling_usd=2.0)

    assert blocker is not None
    assert "settled live-attempt spend" in blocker


def test_live_attempt_guard_force_bypasses_same_day_blocks(tmp_path):
    settings = _settings(tmp_path)
    _write_events(tmp_path, "agent-1", [_attempt("2026-06-14", "started")])

    assert _live_attempt_blocker(settings, as_of="2026-06-14", ceiling_usd=5, force=True) is None
