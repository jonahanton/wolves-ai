"""A live republish must reapply the agent's latent effects, not just its
perturbations; dropping them makes headline numbers sawtooth between the daily
agent run and the cheaper live re-runs."""

from __future__ import annotations

from wolves.live import scan_snapshots
from wolves.snapshot import AgentBlock, FocusTeamBlock, NarrativeBlock, RunMeta, Snapshot, WorldOut


def _agent_snapshot() -> Snapshot:
    worlds = [
        WorldOut(
            name="base",
            weight=1.0,
            perturbations=[],
            latent_effects=[
                {
                    "reason": "star striker fitness in doubt",
                    "targets": {"england": 1.0},
                    "prior": {"kind": "spike_slab", "p_zero": 0.4, "mean": -0.08, "sd": 0.03},
                }
            ],
        )
    ]
    return Snapshot(
        run=RunMeta(
            run_id="agent-1", created_at="2026-07-01T10:00:00+00:00", n_sims=1, engine_version="0.2.0", kind="agent"
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[],
        agent=AgentBlock(narrative=NarrativeBlock(), worlds=worlds),
    )


def test_scan_snapshots_preserves_latent_effects(tmp_path) -> None:
    (tmp_path / "agent-1.json").write_text(_agent_snapshot().model_dump_json(), encoding="utf-8")

    _, worlds = scan_snapshots(tmp_path)

    assert len(worlds) == 1
    assert len(worlds[0].latent_effects) == 1
    assert worlds[0].latent_effects[0].reason == "star striker fitness in doubt"
