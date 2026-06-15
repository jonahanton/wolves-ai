from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from tests.graph.conftest import build_graph_deps
from wolves.run_agent import _attribution_block
from wolves.snapshot import FocusTeamBlock, RunMeta, Snapshot, TeamInfo


def _snapshot(*, run_id: str, kind: str, as_of: str, created_at: str) -> Snapshot:
    return Snapshot(
        run=RunMeta(run_id=run_id, created_at=created_at, as_of=as_of, n_sims=100, engine_version="0", kind=kind),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={"champion": 0.1}, paths=[]),
        slots=[],
        teams=[
            TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=0.1),
            TeamInfo(team_id="france", name="France", group="I", elo=2050, champion_prob=0.08),
        ],
    )


def _write(snapshot: Snapshot, root: Path) -> None:
    day = snapshot.run.as_of
    path = root / "snapshots" / day[:4] / day[5:7] / day[8:10] / f"{snapshot.run.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(), encoding="utf-8")


def test_attribution_prefers_previous_agent_over_newer_live_snapshot(tmp_path, monkeypatch):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-15"
    deps.forecaster = object()
    _write(
        _snapshot(
            run_id="agent-20260613-140248",
            kind="agent",
            as_of="2026-06-13",
            created_at="2026-06-13T14:56:13+00:00",
        ),
        tmp_path,
    )
    _write(
        _snapshot(
            run_id="live-20260614-215610",
            kind="live",
            as_of="2026-06-14",
            created_at="2026-06-14T21:56:10+00:00",
        ),
        tmp_path,
    )
    calls: list[date] = []

    def fake_decompose(*_args, previous_as_of: date, **_kwargs):
        calls.append(previous_as_of)
        return SimpleNamespace(bracket_pp={}, refit_pp={}, residual_pp={})

    monkeypatch.setattr("wolves.run_agent.decompose", fake_decompose)
    monkeypatch.setattr("wolves.run_agent.persisted_results", lambda _settings: {})

    block = _attribution_block(deps, SimpleNamespace(teams=[]))

    assert block is not None
    assert calls == [date(2026, 6, 13)]
    deps.runtime.shutdown()
