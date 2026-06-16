from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission import _validation
from wolves.agent.tools.submission.check_forecast import _check_forecast

SCENARIO_WEIGHTS = [
    {"name": "plays", "weight": 0.6, "rationale": "Keeper plays after training in full."},
    {"name": "out", "weight": 0.4, "rationale": "Keeper absence still carries some squad risk."},
]


@pytest.fixture
def deps(tmp_path: Path) -> AgentDeps:
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="saka mixture",
        payload={
            "weights": {"plays": 0.6, "out": 0.4},
            "worlds": {
                "plays": {"perturbations": []},
                "out": {"perturbations": [{"team": "england", "delta": -0.1, "reason": "saka out"}]},
            },
            "mixture": {"england": 0.066, "rest": 0.934},
        },
    )
    deps.ledger.append(
        claim="Keeper confirmed fit",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="keeper returns",
        team_id="england",
    )
    return deps


@pytest.mark.parametrize(
    ("submission", "expect_ok"),
    [
        pytest.param(build_submission(scenario_weights=SCENARIO_WEIGHTS), True, id="clean-draft"),
        pytest.param(build_submission(artifact_id="mixture-999"), False, id="hard-issue-draft"),
    ],
)
async def test_preview_reports_without_spending_state(deps: AgentDeps, submission, expect_ok: bool):
    result = await _check_forecast(submission, deps)
    deps.runtime.shutdown()
    assert result.ok
    assert result.payload["ok"] is expect_ok
    assert ("escalations" in result.payload) and ("would_pause_for_steelman" in result.payload)
    if not expect_ok:
        assert result.payload["issues"][0]["severity"] == "hard"
    assert deps.submission.accepted is None
    assert deps.submission.validation_failures == 0
    assert deps.submission.escalation_fired is False
    if expect_ok:
        assert deps.submission.checked_clean == submission
        assert deps.submission.copy_repair_required is False
    else:
        assert deps.submission.checked_clean is None


async def test_preview_includes_governed_published_titles(deps: AgentDeps, monkeypatch):
    monkeypatch.setattr(
        _validation,
        "publish_surface",
            lambda _deps, _artifact_id: SimpleNamespace(
                published_titles={"england": 0.082, "france": 0.1, "rest": 0.818},
                raw_titles={"england": 0.066, "france": 0.1, "rest": 0.834},
                baseline_titles={"england": 0.098, "france": 0.1, "rest": 0.802},
                governor_scale=0.5,
                effective_d=0.5,
                governor_active=True,
        ),
    )

    submission = build_submission(scenario_weights=SCENARIO_WEIGHTS)
    result = await _check_forecast(submission, deps)
    deps.runtime.shutdown()

    preview = result.payload["published_preview"]
    assert preview["active"] is True
    assert preview["effective_d"] == 0.5
    assert preview["titles"]["england"] == 0.082
    assert preview["raw_titles"]["england"] == 0.066
    assert preview["ranking"][:2] == [
        {"rank": 1, "team": "rest", "p_title": 0.818, "pct": 81.8},
        {"rank": 2, "team": "france", "p_title": 0.1, "pct": 10.0},
    ]


async def test_preview_reports_unpublishable_artifact_without_tool_error(deps: AgentDeps):
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="typed only",
        payload={"weights": {"model": 1.0}, "mixture": {"england": 0.08}},
    )

    result = await _check_forecast(build_submission(artifact_id="mixture-002"), deps)
    deps.runtime.shutdown()

    assert result.ok
    assert not result.payload["ok"]
    assert result.payload["issues"][0]["code"] == "artifact_unpublishable"


async def test_preview_routes_weight_dilution_back_to_artifact_repair(deps: AgentDeps):
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="split market view",
        payload={
            "weights": {"market_a": 0.35, "market_b": 0.35, "model": 0.3},
            "worlds": {
                "market_a": {"perturbations": [{"team": "spain", "delta": 0.09, "reason": "market"}]},
                "market_b": {"perturbations": [{"team": "spain", "delta": 0.06, "reason": "market"}]},
                "model": {"perturbations": []},
            },
            "mixture": {"spain": 0.17, "rest": 0.83},
        },
    )
    submission = build_submission(
        artifact_id="mixture-002",
        evidence_ids=[],
        scenario_weights=[
            {"name": "market_a", "weight": 0.35, "rationale": "First market view."},
            {"name": "market_b", "weight": 0.35, "rationale": "Second market view."},
            {"name": "model", "weight": 0.3, "rationale": "Model view."},
        ],
    )

    result = await _check_forecast(submission, deps)
    deps.runtime.shutdown()

    assert result.ok
    assert not result.payload["ok"]
    issue = next(issue for issue in result.payload["issues"] if issue["code"] == "weight_dilution")
    assert issue["severity"] == "hard"
    assert "structural artifact issue" in result.payload["next_action"]
    assert "brief quant" in result.payload["next_action"]
