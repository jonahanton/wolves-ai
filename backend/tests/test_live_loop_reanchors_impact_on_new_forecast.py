from __future__ import annotations

import asyncio
from types import SimpleNamespace

from wolves.config import Settings as EngineSettings
from wolves_backend.jobs import LiveLoop
from wolves_backend.models import SnapshotRef


def _ref(run_id: str, kind: str) -> SnapshotRef:
    return SnapshotRef(run_id=run_id, as_of="2026-06-19", kind=kind, key=f"snapshots/2026/06/19/{run_id}.json")


def _loop(tmp_path, *, newest_agent: str | None, anchored: str | None) -> LiveLoop:
    settings = EngineSettings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    refs = [_ref("live-20260619-025728", "live")]
    if newest_agent is not None:
        refs.append(_ref(newest_agent, "agent"))
    snapshots = SimpleNamespace(index=lambda: _async(refs))
    impact = SimpleNamespace(anchored_run_id=lambda: anchored)
    engine = SimpleNamespace(settings=settings, ready=True)
    deps = SimpleNamespace(engine=engine, snapshots=snapshots, impact=impact)
    return LiveLoop(deps=deps, alerts=SimpleNamespace())


async def _async(value):
    return value


def test_idle_collapses_to_poll_when_a_newer_agent_forecast_is_unanchored(tmp_path):
    loop = _loop(tmp_path, newest_agent="agent-20260619-101015", anchored="agent-20260618-101744")
    loop._interval = lambda: loop._settings.live_idle_interval_s
    assert asyncio.run(loop._sleep_interval()) == loop._settings.live_poll_interval_s


def test_idle_holds_when_impact_already_anchored_to_newest(tmp_path):
    loop = _loop(tmp_path, newest_agent="agent-20260619-101015", anchored="agent-20260619-101015")
    loop._interval = lambda: loop._settings.live_idle_interval_s
    assert asyncio.run(loop._sleep_interval()) == loop._settings.live_idle_interval_s


def test_fast_cadence_is_never_lengthened(tmp_path):
    loop = _loop(tmp_path, newest_agent="agent-20260619-101015", anchored="agent-20260618-101744")
    loop._interval = lambda: loop._settings.live_poll_interval_s
    assert asyncio.run(loop._sleep_interval()) == loop._settings.live_poll_interval_s


def test_index_failure_falls_back_to_the_idle_cadence(tmp_path):
    loop = _loop(tmp_path, newest_agent="agent-20260619-101015", anchored="agent-20260618-101744")
    loop._interval = lambda: loop._settings.live_idle_interval_s

    def _boom():
        raise RuntimeError("s3 down")

    loop._deps.snapshots.index = _boom
    assert asyncio.run(loop._sleep_interval()) == loop._settings.live_idle_interval_s
