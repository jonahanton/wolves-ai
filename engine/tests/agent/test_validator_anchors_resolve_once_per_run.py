from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.tools.submission import _validation
from wolves.sim.api import SimOutputs
from wolves.snapshot import FocusTeamBlock, RunMeta, Snapshot, TeamInfo


class _ReplayForecaster:
    def played_results(self, extra_results=None):
        return {}

    def simulate(self, *, perturbations=(), **_kwargs):
        return "branch" if perturbations else "base"

    def sim_outputs(self, *, result, n_sims, seed, **_kwargs):
        return _outputs(p_england=0.2 if result == "branch" else 0.1, n_sims=n_sims, seed=seed)


def _outputs(*, p_england: float, n_sims: int, seed: int) -> SimOutputs:
    return SimOutputs(
        n_sims=n_sims,
        seed=seed,
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[
            TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=p_england),
            TeamInfo(team_id="france", name="France", group="D", elo=2000, champion_prob=1 - p_england),
        ],
        groups=[],
        matches=[],
    )


def test_baseline_and_market_anchors_compute_once_across_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deps = build_graph_deps(tmp_path)
    calls: list[str] = []

    def baseline(_deps) -> dict[str, float]:
        calls.append("baseline")
        return {"england": 0.1}

    def market(_deps) -> None:
        calls.append("market")
        return None

    monkeypatch.setattr(_validation, "_baseline_titles", baseline)
    monkeypatch.setattr(_validation, "_market_titles", market)

    _validation.validation_report(build_submission(), deps)
    _validation.validation_report(build_submission(), deps)
    deps.runtime.shutdown()

    assert calls == ["baseline", "market"]


def _snapshot(*, run_id: str, kind: str, p_title: float) -> Snapshot:
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at="2026-06-13T12:00:00+00:00",
            as_of="2026-06-13",
            n_sims=100,
            engine_version="0",
            kind=kind,
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=p_title)],
    )


def test_previous_titles_uses_agent_snapshot_not_later_live(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "agent-20260613-120000.json").write_text(
        _snapshot(run_id="agent-20260613-120000", kind="agent", p_title=0.08).model_dump_json()
    )
    (snapshot_dir / "live-20260613-210000.json").write_text(
        _snapshot(run_id="live-20260613-210000", kind="live", p_title=0.12).model_dump_json()
    )

    assert _validation._previous_titles(deps) == {"england": 0.08}
    deps.runtime.shutdown()


def test_published_preview_uses_publish_surface_not_stored_mixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="mixture",
        created_by="quant",
        summary="stored stale table",
        payload={
            "weights": {"base": 1.0},
            "worlds": {"base": {"perturbations": []}},
            "mixture": {"spain": 0.99},
        },
    )

    def replayed_surface(_deps, artifact_id: str):
        return SimpleNamespace(
            published_titles={"spain": 0.1638},
            raw_titles={"spain": 0.1719},
            baseline_titles={"spain": 0.155},
            governor_scale=1.0,
            effective_d=1.0,
            governor_active=False,
        )

    monkeypatch.setattr(_validation, "publish_surface", replayed_surface)

    preview = _validation.published_title_preview(deps, "mixture-001")
    deps.runtime.shutdown()

    assert preview["titles"] == {"spain": 0.1638}
    assert preview["raw_titles"] == {"spain": 0.1719}


def test_published_preview_replays_worlds_when_stored_mixture_is_stale(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    deps.forecaster = _ReplayForecaster()
    deps.artifacts.add(
        kind="mixture",
        created_by="quant",
        summary="stored stale table",
        payload={
            "weights": {"base": 0.6, "branch": 0.4},
            "worlds": {
                "base": {"perturbations": []},
                "branch": {"perturbations": [{"team": "england", "delta": 0.1, "reason": "branch"}]},
            },
            "mixture": {"england": 0.99, "france": 0.01},
        },
    )

    preview = _validation.published_title_preview(deps, "mixture-001")
    deps.runtime.shutdown()

    assert preview["titles"]["england"] == pytest.approx(0.14)
    assert preview["titles"]["france"] == pytest.approx(0.86)


def test_branch_advisories_are_visible_but_not_validator_issues(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="evidence",
        created_by="research",
        summary="France market premium branch",
        payload={
            "summary": "France branch found.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "Market is right about France.",
                    "support": "Current odds stay high.",
                    "collapse_condition": "Gap falls inside uncertainty.",
                    "source_ids": [],
                    "confidence": "medium",
                    "suggested_quant_question": "Price the France market premium.",
                }
            ],
        },
    )
    deps.artifacts.add(
        kind="mixture",
        created_by="quant",
        summary="generic evidence worlds",
        payload={
            "weights": {"model_base": 0.7, "market_evidence": 0.3},
            "worlds": {"model_base": {"perturbations": []}, "market_evidence": {"perturbations": []}},
            "mixture": {"france": 0.15, "england": 0.85},
        },
    )

    advisories = _validation.branch_advisories(deps, "mixture-001")
    report = _validation.validation_report(build_submission(), deps)
    deps.runtime.shutdown()

    assert {item["code"] for item in advisories} == {
        "candidate_branches_unaccounted",
        "generic_world_metadata_missing",
    }
    assert "candidate_branches_unaccounted" not in report.summary()


def test_branch_advisories_warn_when_audit_omits_candidate_branch(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="evidence",
        created_by="research",
        summary="France market premium branch",
        payload={
            "summary": "France branch found.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "Market is right about France.",
                    "support": "Current odds stay high.",
                    "collapse_condition": "Gap falls inside uncertainty.",
                    "source_ids": [],
                    "confidence": "medium",
                    "suggested_quant_question": "Price the France market premium.",
                }
            ],
        },
    )
    deps.artifacts.add(
        kind="mixture",
        created_by="quant",
        summary="audited other branch",
        payload={
            "weights": {"model_base": 1.0},
            "worlds": {"model_base": {"perturbations": []}},
            "mixture": {"france": 0.15, "england": 0.85},
            "branch_audit": {
                "verdict": "Other branch checked.",
                "checks": [
                    {
                        "key": "spain-availability",
                        "status": "rejected",
                        "hypothesis": "Spain availability matters.",
                        "summary": "Rejected.",
                    }
                ],
            },
        },
    )

    advisories = _validation.branch_advisories(deps, "mixture-001")
    deps.runtime.shutdown()

    assert [item["code"] for item in advisories] == ["candidate_branches_missing_from_audit"]
    assert "france-market-premium" in advisories[0]["message"]
