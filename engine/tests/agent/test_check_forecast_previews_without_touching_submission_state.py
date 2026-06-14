from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.deps import AgentDeps
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
