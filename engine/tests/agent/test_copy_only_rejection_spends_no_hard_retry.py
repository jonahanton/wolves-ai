from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission.submit_forecast import _submit_forecast

SCENARIO_WEIGHTS = [
    {"name": "plays", "weight": 0.6, "rationale": "Keeper plays after training in full."},
    {"name": "out", "weight": 0.4, "rationale": "Keeper absence still carries some squad risk."},
]

COPY_ONLY = build_submission(
    narrative=build_narrative(headline="England look sharp — and the camp is calm."),
    scenario_weights=SCENARIO_WEIGHTS,
)
HARD = build_submission(artifact_id="mixture-999")


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
    ("submission", "expected_failures"),
    [
        pytest.param(COPY_ONLY, 0, id="copy-only-rejection-is-free"),
        pytest.param(HARD, 1, id="hard-rejection-spends-a-retry"),
    ],
)
async def test_only_hard_issues_consume_a_retry(deps: AgentDeps, submission, expected_failures: int):
    result = await _submit_forecast(submission, deps)
    deps.runtime.shutdown()
    assert not result.ok
    assert deps.submission.accepted is None
    assert deps.submission.validation_failures == expected_failures
    assert deps.submission.copy_repair_required is (expected_failures == 0)
