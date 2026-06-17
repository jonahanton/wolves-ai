from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.tools.submission import _validation
from wolves.agent.tools.submission.check_forecast import _check_forecast
from wolves.agent.tools.submission.normalise import normalise_submission


def _deps_with_artifact(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    artifact = deps.artifacts.add(
        kind="mixture",
        created_by="quant",
        summary="audited mixture",
        payload={
            "weights": {"model_base": 0.5, "market_base": 0.5},
            "worlds": {"model_base": {"perturbations": []}, "market_base": {"perturbations": []}},
            "mixture": {"england": 0.086, "portugal": 0.084, "rest": 0.83},
            "factor_audit": {
                "checks": [
                    {
                        "key": "market_gap",
                        "status": "checked",
                        "summary": "England market gap checked.",
                        "teams": ["england"],
                    }
                ]
            },
        },
    )
    return deps, artifact.id


def test_finalisation_replaces_single_stale_story_percentage(tmp_path: Path, monkeypatch):
    deps, artifact_id = _deps_with_artifact(tmp_path)
    monkeypatch.setattr(
        _validation,
        "publish_surface",
        lambda _deps, _artifact_id: SimpleNamespace(
            published_titles={"england": 0.086, "portugal": 0.084, "rest": 0.83},
            raw_titles={"england": 0.086, "portugal": 0.084, "rest": 0.83},
            baseline_titles={"england": 0.08, "portugal": 0.08, "rest": 0.84},
            governor_scale=1.0,
            effective_d=1.0,
            governor_active=False,
        ),
    )
    submission = build_submission(
        artifact_id=artifact_id,
        narrative=build_narrative(
            team_stories={
                "portugal": {
                    "summary": "Portugal sit at 10.4% after the market read.",
                    "why": "Their draw is still manageable.",
                }
            }
        ),
    )

    result = normalise_submission(submission, deps)
    deps.runtime.shutdown()

    assert result.submission.narrative.team_stories["portugal"].summary == (
        "Portugal sit at 8.4% after the market read."
    )
    assert result.warnings == ["stripped non-published percentages from team story summaries for: portugal"]


def test_finalisation_trims_market_gaps_to_audited_teams(tmp_path: Path):
    deps, artifact_id = _deps_with_artifact(tmp_path)
    submission = build_submission(
        artifact_id=artifact_id,
        market_gaps=[
            {"team_id": "england", "model_prob": 0.086, "market_prob": 0.11, "gap_pp": 2.4},
            {"team_id": "portugal", "model_prob": 0.084, "market_prob": 0.104, "gap_pp": 2.0},
        ],
    )

    result = normalise_submission(submission, deps)
    deps.runtime.shutdown()

    assert [gap.team_id for gap in result.submission.market_gaps] == ["england"]
    assert result.warnings == ["removed market_gaps not covered by the factor_audit market_gap row: portugal"]


async def test_repeated_copy_only_preview_blocks_repair_loop(tmp_path: Path):
    deps, artifact_id = _deps_with_artifact(tmp_path)
    submission = build_submission(
        artifact_id=artifact_id,
        narrative=build_narrative(headline="England look sharp \u2014 and the camp is calm."),
        scenario_weights=[
            {"name": "model_base", "weight": 0.5, "rationale": "The fitted model remains live."},
            {"name": "market_base", "weight": 0.5, "rationale": "The market read remains live."},
        ],
        evidence_ids=[],
    )

    for _ in range(3):
        result = await _check_forecast(submission, deps)
    deps.runtime.shutdown()

    assert result.payload["copy_issue_repeats"] == 3
    assert deps.submission.copy_repair_blocked is True
    assert "Stop this forecast attempt" in result.payload["next_action"]
