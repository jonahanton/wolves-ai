from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.graph.artifacts import RunArtifactStore


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="Keeper confirmed fit",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="keeper returns",
        team_id="england",
    )
    return ledger


@pytest.fixture
def store(tmp_path: Path) -> RunArtifactStore:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="saka mixture",
        payload={
            "weights": {"plays": 0.6, "out": 0.4},
            "worlds": {
                "plays": {"perturbations": []},
                "out": {"perturbations": [{"team": "england", "delta": -0.1, "reason": "saka out"}]},
            },
            "mixture": {"england": 0.066, "spain": 0.187, "rest": 0.747},
        },
    )
    return store


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def _validate(submission, store, ledger, **kwargs):
    return validate_submission(submission, artifacts=store, ledger=ledger, limits=ValidatorLimits(), **kwargs)


def test_em_dash_anywhere_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    story = "England look sharp — and the camp is calm."
    submission = build_submission(narrative=build_narrative(focus_story=story))
    assert "em_dash" in _codes(_validate(submission, store, ledger))


def test_missing_slot_rationales_reject(store: RunArtifactStore, ledger: EvidenceLedger):
    narrative = build_narrative(slot_rationales={"73": "favourite advances"})
    submission = build_submission(narrative=narrative)
    assert "slot_rationales_incomplete" in _codes(_validate(submission, store, ledger))


def test_typed_probabilities_never_publish(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(artifact_id="mixture-999")
    report = _validate(submission, store, ledger)
    assert "unknown_artifact" in _codes(report)
    assert "never typed probabilities" in report.summary()


def test_pinned_scoreline_worlds_never_publish(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="what if",
        payload={
            "weights": {"pinned": 1.0},
            "worlds": {
                "pinned": {"perturbations": [{"match": 22, "home_goals": 2, "away_goals": 0, "reason": "what if"}]}
            },
            "mixture": {"england": 0.08},
        },
    )
    submission = build_submission(artifact_id="mixture-002")
    assert "artifact_unpublishable" in _codes(_validate(submission, store, ledger))


def test_incoherent_mixture_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="broken",
        payload={"mixture": {"england": 0.4, "spain": 0.2}},
    )
    submission = build_submission(artifact_id="mixture-002")
    assert "partition_incoherent" in _codes(_validate(submission, store, ledger))


def test_rumour_cited_weight_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    ledger.append(
        claim="dressing room unrest",
        source_url="https://www.goal.com/x",
        status="rumour",
        mechanism="morale",
    )
    submission = build_submission(scenario_weights=[{"name": "unrest", "weight": 1.0, "ledger_ids": ["led-0002"]}])
    assert "rumour_cited" in _codes(_validate(submission, store, ledger))
