from __future__ import annotations

import asyncio
from types import SimpleNamespace

from wolves.config import Settings as EngineSettings
from wolves_backend import jobs
from wolves_backend.jobs import LiveLoop
from wolves_backend.models import SnapshotRef


def _ref(run_id: str, kind: str) -> SnapshotRef:
    return SnapshotRef(run_id=run_id, as_of="2026-06-19", kind=kind, key=f"snapshots/2026/06/19/{run_id}.json")


class _Sleeps:
    """Records each sleep without waiting, firing a hook on the Nth call."""

    def __init__(self, *, on_call: int | None = None, hook=None) -> None:
        self.durations: list[float] = []
        self._on_call = on_call
        self._hook = hook

    async def __call__(self, seconds: float) -> None:
        self.durations.append(seconds)
        if self._on_call is not None and len(self.durations) == self._on_call and self._hook is not None:
            self._hook()


def _loop(tmp_path, *, refs: list[SnapshotRef], anchored: str | None, fast: bool = False) -> LiveLoop:
    settings = EngineSettings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    probe_calls = {"count": 0}

    async def _index_for(_day):
        probe_calls["count"] += 1
        return list(refs)

    snapshots = SimpleNamespace(index_for=_index_for)
    impact = SimpleNamespace(anchored_run_id=lambda: anchored)
    engine = SimpleNamespace(settings=settings, ready=True)
    deps = SimpleNamespace(engine=engine, snapshots=snapshots, impact=impact)
    loop = LiveLoop(deps=deps, alerts=SimpleNamespace())
    loop._interval = lambda: settings.live_poll_interval_s if fast else settings.live_idle_interval_s
    loop._probe_calls = probe_calls  # type: ignore[attr-defined]
    return loop


def test_new_forecast_mid_idle_returns_within_one_chunk(tmp_path, monkeypatch):
    refs = [_ref("agent-20260618-101744", "agent")]
    loop = _loop(tmp_path, refs=refs, anchored="agent-20260618-101744")
    sleeps = _Sleeps(on_call=3, hook=lambda: refs.insert(0, _ref("agent-20260619-101015", "agent")))
    monkeypatch.setattr(jobs.asyncio, "sleep", sleeps)

    asyncio.run(loop._idle_wait())

    assert sleeps.durations == [loop._settings.impact_anchor_probe_interval_s] * 3


def test_idle_elapses_fully_when_no_new_forecast(tmp_path, monkeypatch):
    refs = [_ref("agent-20260619-101015", "agent")]
    loop = _loop(tmp_path, refs=refs, anchored="agent-20260619-101015")
    chunk = loop._settings.impact_anchor_probe_interval_s
    loop._interval = lambda: chunk * 2.5
    sleeps = _Sleeps()
    monkeypatch.setattr(jobs.asyncio, "sleep", sleeps)

    asyncio.run(loop._idle_wait())

    assert sleeps.durations == [chunk, chunk, chunk * 0.5]


def test_fast_cadence_sleeps_once_without_probing(tmp_path, monkeypatch):
    refs = [_ref("agent-20260619-101015", "agent")]
    loop = _loop(tmp_path, refs=refs, anchored="agent-20260618-101744", fast=True)
    sleeps = _Sleeps()
    monkeypatch.setattr(jobs.asyncio, "sleep", sleeps)

    asyncio.run(loop._idle_wait())

    assert sleeps.durations == [loop._settings.live_poll_interval_s]
    assert loop._probe_calls["count"] == 0


def test_probe_failure_lets_idle_elapse(tmp_path, monkeypatch):
    loop = _loop(tmp_path, refs=[], anchored="agent-20260618-101744")

    async def _boom(_day):
        raise RuntimeError("s3 down")

    loop._deps.snapshots.index_for = _boom
    sleeps = _Sleeps()
    monkeypatch.setattr(jobs.asyncio, "sleep", sleeps)

    asyncio.run(loop._idle_wait())

    assert sum(sleeps.durations) == loop._settings.live_idle_interval_s
