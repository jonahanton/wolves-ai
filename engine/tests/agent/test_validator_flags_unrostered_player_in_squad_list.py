from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.graph.artifacts import RunArtifactStore

_ROSTER = frozenset({"bellingham", "saka", "kane", "rashford", "rice"})
_TEAMS = frozenset({"england", "croatia", "spain", "france", "brazil"})


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    return EvidenceLedger(tmp_path / "ledger.jsonl")


@pytest.fixture
def store(tmp_path: Path) -> RunArtifactStore:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="england mixture",
        payload={
            "weights": {"plays": 0.6, "out": 0.4},
            "worlds": {"plays": {"perturbations": []}, "out": {"perturbations": []}},
            "mixture": {"england": 0.112, "spain": 0.187, "rest": 0.701},
        },
    )
    return store


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def _validate(submission, store, ledger):
    return validate_submission(
        submission,
        artifacts=store,
        ledger=ledger,
        limits=ValidatorLimits(),
        roster_tokens=_ROSTER,
        team_tokens=_TEAMS,
    )


def test_unrostered_name_in_squad_list_flags_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "england": {
                    "summary": "England hold steady on our published numbers.",
                    "why": "The squad-value uplift for Bellingham, Saka and Palmer is priced across all worlds.",
                }
            }
        )
    )

    report = _validate(submission, store, ledger)
    roster = [i for i in report.issues if i.code == "roster_name_unverified"]

    assert roster and all(i.severity == "copy" for i in roster)
    assert "Palmer" in roster[0].message


def test_real_squad_list_does_not_flag(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "england": {
                    "summary": "England beat Croatia with goals from Kane, Bellingham and Rashford.",
                    "why": "The win is in the model and the rating stands on the squad's strength.",
                }
            }
        )
    )

    assert "roster_name_unverified" not in _codes(_validate(submission, store, ledger))


def test_lone_left_behind_player_does_not_flag(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "england": {
                    "summary": "England look settled despite a notable omission.",
                    "why": "Cole Palmer was left out of the squad entirely, which the rating already reflects.",
                }
            }
        )
    )

    assert "roster_name_unverified" not in _codes(_validate(submission, store, ledger))


def test_team_name_list_does_not_flag(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        narrative=build_narrative(headline="Spain, France and Brazil remain the clear contenders at the top.")
    )

    assert "roster_name_unverified" not in _codes(_validate(submission, store, ledger))


def test_authoritative_only_player_is_accepted(store: RunArtifactStore, ledger: EvidenceLedger):
    """A name present in the authoritative roster but absent from the
    Transfermarkt pull (e.g. a late call-up) must not flag: the guard unions
    both sources."""
    submission = build_submission(
        narrative=build_narrative(
            team_stories={
                "brazil": {
                    "summary": "Brazil rotate their attack against tired legs.",
                    "why": "Fresh options through Endrick, Rayan and Wesley keep the press intact.",
                }
            }
        )
    )

    report = validate_submission(
        submission,
        artifacts=store,
        ledger=ledger,
        limits=ValidatorLimits(),
        roster_tokens=frozenset({"endrick", "rayan", "wesley"}),
        team_tokens=frozenset({"brazil"}),
    )

    assert "roster_name_unverified" not in _codes(report)
