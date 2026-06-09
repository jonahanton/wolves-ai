from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission


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


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_em_dash_anywhere_rejects(ledger: EvidenceLedger):
    story = "England look sharp — and the camp is calm."
    submission = build_submission(narrative=build_narrative(england_story=story))
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "em_dash" in _codes(report)


def test_missing_slot_rationales_reject(ledger: EvidenceLedger):
    narrative = build_narrative(slot_rationales={"73": "favourite advances"})
    submission = build_submission(narrative=narrative)
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "slot_rationales_incomplete" in _codes(report)


def test_reach_probabilities_must_not_increase_through_rounds(ledger: EvidenceLedger):
    submission = build_submission(england_reach_probs={"r32": 0.5, "r16": 0.7})
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "probs_incoherent" in _codes(report)


def test_fixture_offsets_require_iso_expiry(ledger: EvidenceLedger):
    submission = build_submission(
        fixture_offsets=[{"match": 40, "home_goals": -0.2, "away_goals": 0.0, "expiry": "soon"}]
    )
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "offset_expiry_invalid" in _codes(report)


def test_market_divergence_above_threshold_needs_justification(ledger: EvidenceLedger):
    submission = build_submission(delta_vs_market=0.08, market_justification="")
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "market_justification_missing" in _codes(report)

    justified = build_submission(delta_vs_market=0.08, market_justification="Confirmed keeper news the books lag.")
    assert validate_submission(justified, ledger=ledger, limits=ValidatorLimits()).ok
