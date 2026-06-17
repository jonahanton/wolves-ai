from __future__ import annotations

from pathlib import Path

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.source_memory import SourceMemory
from wolves.insights.what_changed import what_changed
from wolves.snapshot import FocusTeamBlock, RunMeta, Snapshot, TeamInfo


def _snapshot() -> Snapshot:
    return Snapshot(
        run=RunMeta(
            run_id="agent-d1", created_at="2026-06-09T08:00:00+00:00", n_sims=1000, engine_version="x", kind="agent"
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={"champion": 0.07}, paths=[]),
        slots=[],
        teams=[
            TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=0.07),
            TeamInfo(team_id="france", name="France", group="I", elo=2050, champion_prob=0.085),
        ],
    )


def test_diff_reports_moves_expiries_and_new_sources(tmp_path: Path):
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="keeper doubt",
        source_url="https://reuters.com/a",
        status="probable",
        mechanism="lineup",
        expiry="2026-06-09T23:59:59Z",
    )
    memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    memory.record("https://example.com/new", run_id="agent-d2", disposition="fetched")
    memory.record("https://example.com/old", run_id="agent-d1", disposition="fetched")

    diff = what_changed(
        previous=_snapshot(),
        current_titles={"england": 0.072, "france": 0.07},
        ledger=ledger,
        source_memory=memory,
        run_id="agent-d2",
        as_of="2026-06-10",
        move_floor_pp=0.3,
    )

    assert diff.previous_run_id == "agent-d1"
    assert list(diff.title_moves_pp) == ["france"]
    assert diff.title_moves_pp["france"] == -1.5
    assert diff.new_sources == ["https://example.com/new"]
    assert diff.expired_evidence == ["led-0001"]
    assert "france -1.5pp" in diff.digest()


def test_no_previous_run_degrades(tmp_path: Path):
    diff = what_changed(
        previous=None,
        current_titles=None,
        ledger=EvidenceLedger(tmp_path / "l.jsonl"),
        source_memory=None,
        run_id="agent-d1",
        as_of="2026-06-10",
    )
    assert diff.digest() == "No previous run to diff against."
