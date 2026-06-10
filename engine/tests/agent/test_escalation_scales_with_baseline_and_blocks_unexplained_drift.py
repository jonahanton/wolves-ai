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
        created_by="quant-1",
        summary="mixture",
        payload={"mixture": {"england": 0.10, "ghana": 0.012, "rest": 0.888}},
    )
    return store


def _ledger(tmp_path: Path) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(claim="keeper fit", source_url="https://www.thefa.com/news", status="confirmed", mechanism="lineup")
    return ledger


def _validate(submission, store, ledger, **kwargs):
    return validate_submission(submission, artifacts=store, ledger=ledger, limits=ValidatorLimits(), **kwargs)


def test_escalation_threshold_scales_proportionally_below_ten_percent(store: RunArtifactStore, tmp_path: Path):
    ledger = _ledger(tmp_path)
    baseline = {"england": 0.072, "ghana": 0.004, "rest": 0.924}

    report = _validate(build_submission(), store, ledger, baseline_titles=baseline)

    assert report.ok
    # England +2.8pp breaches the flat 2pp threshold; Ghana +0.8pp breaches
    # its scaled threshold (2pp * 0.004/0.10, floored at 0.10pp).
    assert any(e.startswith("england") for e in report.escalations)
    assert any(e.startswith("ghana") for e in report.escalations)


def test_unexplained_drift_vs_previous_published_rejects(store: RunArtifactStore, tmp_path: Path):
    ledger = _ledger(tmp_path)
    previous = {"england": 0.072, "ghana": 0.012, "rest": 0.916}

    silent = _validate(build_submission(), store, ledger, previous_titles=previous)
    assert not silent.ok
    assert any(i.code == "unexplained_drift" for i in silent.issues)

    acknowledged = _validate(
        build_submission(inconsistency_note="Yesterday under-weighted the keeper news; corrected today."),
        store,
        ledger,
        previous_titles=previous,
    )
    assert acknowledged.ok
