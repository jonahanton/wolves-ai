from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from wolves.agent.contracts import RatingOverride
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="Keeper confirmed fit by the FA",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="first-choice keeper returns",
        proposed_delta=15.0,
        team_id="england",
    )
    ledger.append(
        claim="Striker doubtful per beat reporter",
        source_url="https://www.theathletic.com/article",
        status="probable",
        mechanism="possible absence of starting striker",
        proposed_delta=-8.0,
        team_id="france",
    )
    ledger.append(
        claim="Dressing-room rift rumoured",
        source_url="https://example.com/gossip",
        status="rumour",
        mechanism="morale",
        team_id="spain",
    )
    return ledger


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_valid_submission_passes(ledger: EvidenceLedger):
    report = validate_submission(build_submission(), ledger=ledger, limits=ValidatorLimits())
    assert report.ok, report.summary()


def test_confirmed_single_cause_cannot_exceed_fifty_elo(ledger: EvidenceLedger):
    submission = build_submission(
        rating_overrides=[RatingOverride(team_id="england", delta_elo=60.0, cause="keeper", ledger_ids=["led-0001"])]
    )
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "confirmed_cap_exceeded" in _codes(report)


def test_soft_evidence_total_capped_at_ten_elo_per_team(ledger: EvidenceLedger):
    submission = build_submission(
        rating_overrides=[
            RatingOverride(team_id="france", delta_elo=-7.0, cause="striker doubt", ledger_ids=["led-0002"]),
            RatingOverride(team_id="france", delta_elo=-6.0, cause="same doubt again", ledger_ids=["led-0002"]),
        ]
    )
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "soft_cap_exceeded" in _codes(report)


def test_rumours_justify_zero_delta_only(ledger: EvidenceLedger):
    submission = build_submission(
        rating_overrides=[RatingOverride(team_id="spain", delta_elo=-5.0, cause="rift", ledger_ids=["led-0003"])]
    )
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert "uncited_delta" in _codes(report)

    zero = build_submission(
        rating_overrides=[RatingOverride(team_id="spain", delta_elo=0.0, cause="rift noted", ledger_ids=["led-0003"])]
    )
    assert validate_submission(zero, ledger=ledger, limits=ValidatorLimits()).ok


def test_unknown_ledger_id_rejected(ledger: EvidenceLedger):
    submission = build_submission(
        rating_overrides=[RatingOverride(team_id="england", delta_elo=10.0, cause="x", ledger_ids=["led-9999"])]
    )
    report = validate_submission(submission, ledger=ledger, limits=ValidatorLimits())
    assert {"unknown_ledger_id", "uncited_delta"} <= _codes(report)


def test_governor_scale_halves_the_caps(ledger: EvidenceLedger):
    submission = build_submission(
        rating_overrides=[RatingOverride(team_id="england", delta_elo=30.0, cause="keeper", ledger_ids=["led-0001"])]
    )
    assert validate_submission(submission, ledger=ledger, limits=ValidatorLimits()).ok
    halved = ValidatorLimits(delta_cap_scale=0.5)
    report = validate_submission(submission, ledger=ledger, limits=halved)
    assert "confirmed_cap_exceeded" in _codes(report)
