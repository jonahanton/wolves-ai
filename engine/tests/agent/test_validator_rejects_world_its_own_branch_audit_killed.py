from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.graph.artifacts import RunArtifactStore


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger(tmp_path / "ledger.jsonl")


def _store_with_branch_audit(tmp_path: Path, *, status: str) -> RunArtifactStore:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="france branch",
        payload={
            "weights": {"model_base": 0.7, "france_gap": 0.3},
            "worlds": {
                "model_base": {"perturbations": []},
                "france_gap": {"perturbations": [{"team": "france", "delta": 0.08, "reason": "market gap"}]},
            },
            "mixture": {"france": 0.15, "england": 0.08, "rest": 0.77},
            "branch_audit": {
                "verdict": "France gap adjudicated.",
                "checks": [
                    {
                        "key": "france-market-premium",
                        "status": status,
                        "hypothesis": "The market over-prices France.",
                        "summary": "France premium sits inside the noise floor.",
                        "world_names": ["france_gap"],
                    }
                ],
            },
        },
    )
    return store


def _submission():
    return build_submission(
        artifact_id="mixture-001",
        scenario_weights=[
            {"name": "model_base", "weight": 0.7, "rationale": "Model base remains live."},
            {"name": "france_gap", "weight": 0.3, "rationale": "France gap remains live."},
        ],
    )


@pytest.mark.parametrize("status", ["below_floor", "collapsed", "rejected"])
def test_killed_branch_keeping_a_weighted_world_is_a_hard_block(
    tmp_path: Path, ledger: EvidenceLedger, status: str
):
    store = _store_with_branch_audit(tmp_path, status=status)
    report = validate_submission(_submission(), artifacts=store, ledger=ledger, limits=ValidatorLimits())
    issue = next((i for i in report.issues if i.code == "branch_audit_self_inconsistent"), None)
    assert issue is not None and issue.severity == "hard"
    assert "france_gap" in issue.message


def test_priced_branch_keeping_its_world_is_consistent(tmp_path: Path, ledger: EvidenceLedger):
    store = _store_with_branch_audit(tmp_path, status="priced")
    report = validate_submission(_submission(), artifacts=store, ledger=ledger, limits=ValidatorLimits())
    assert "branch_audit_self_inconsistent" not in {i.code for i in report.issues}
