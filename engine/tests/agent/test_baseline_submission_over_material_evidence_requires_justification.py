from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.graph.artifacts import RunArtifactStore


@pytest.fixture
def store(tmp_path: Path) -> RunArtifactStore:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="runtime",
        summary="baseline",
        payload={"weights": {"baseline": 1.0}, "worlds": {"baseline": {"perturbations": []}}, "mixture": {}},
    )
    return store


def _ledger(tmp_path: Path, *, delta: float) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="Davies ruled out of the group stage",
        source_url="https://www.tsn.ca/davies",
        status="confirmed",
        mechanism="left-back absence",
        proposed_delta=delta,
        team_id="canada",
    )
    return ledger


def _codes(submission, store, ledger) -> set[str]:
    report = validate_submission(submission, artifacts=store, ledger=ledger, limits=ValidatorLimits())
    return {issue.code for issue in report.issues}


def test_silent_baseline_over_material_delta_rejects(store: RunArtifactStore, tmp_path: Path):
    submission = build_submission(evidence_ids=[])
    assert "evidence_unpriced" in _codes(submission, store, _ledger(tmp_path, delta=-1.2))


def test_justified_baseline_passes(store: RunArtifactStore, tmp_path: Path):
    submission = build_submission(
        evidence_ids=[], change_justification="Priced Davies at -1.2pp; below the 1.4pp noise floor at 10k sims."
    )
    assert "evidence_unpriced" not in _codes(submission, store, _ledger(tmp_path, delta=-1.2))


def test_immaterial_evidence_never_blocks_the_baseline(store: RunArtifactStore, tmp_path: Path):
    submission = build_submission(evidence_ids=[])
    assert "evidence_unpriced" not in _codes(submission, store, _ledger(tmp_path, delta=0.2))
