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
    headline = "England look sharp — and the camp is calm."
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert "em_dash" in _codes(_validate(submission, store, ledger))


def test_american_spelling_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "England's favorable draw and organized defense set up a calm opener."
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert "american_spelling" in _codes(_validate(submission, store, ledger))


def test_multi_world_artifact_needs_matching_scenario_weights(store: RunArtifactStore, ledger: EvidenceLedger):
    missing = _validate(build_submission(), store, ledger)
    assert "scenario_weights_missing" in _codes(missing)

    wrong = build_submission(
        scenario_weights=[
            {"name": "plays", "weight": 0.7, "rationale": "Keeper plays after training in full."},
            {"name": "out", "weight": 0.3, "rationale": "Keeper absence still carries some squad risk."},
        ]
    )
    report = _validate(wrong, store, ledger)

    assert "scenario_weights_mismatch" in _codes(report)
    assert "wrong weight for out, plays" in report.summary()


def test_generic_camps_need_one_declaration_per_used_key(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        scenario_weights=[
            {
                "name": "plays",
                "weight": 0.6,
                "rationale": "Keeper plays after training in full.",
                "camp": "keeper-fit",
            },
            {
                "name": "out",
                "weight": 0.4,
                "rationale": "Keeper absence still carries some squad risk.",
                "camp": "keeper-out",
            },
        ],
        camps=[
            {
                "key": "keeper-fit",
                "label": "Keeper fit",
                "summary": "The first-choice goalkeeper starts.",
                "order": 0,
            }
        ],
    )
    report = _validate(submission, store, ledger)

    assert "camp_missing" in _codes(report)
    assert "keeper-out" in report.summary()


def test_matching_non_market_camps_pass_the_contract(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(
        scenario_weights=[
            {
                "name": "plays",
                "weight": 0.6,
                "rationale": "Keeper plays after training in full.",
                "camp": "keeper-fit",
            },
            {
                "name": "out",
                "weight": 0.4,
                "rationale": "Keeper absence still carries some squad risk.",
                "camp": "keeper-out",
            },
        ],
        camps=[
            {
                "key": "keeper-fit",
                "label": "Keeper fit",
                "summary": "The first-choice goalkeeper starts.",
                "order": 0,
            },
            {
                "key": "keeper-out",
                "label": "Keeper out",
                "summary": "The defence plays without its first-choice goalkeeper.",
                "order": 1,
            },
        ],
    )
    report = _validate(submission, store, ledger)

    assert not {"scenario_weights_missing", "scenario_weights_mismatch", "camp_missing"} & _codes(report)


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


def test_missing_headline_rejects(store: RunArtifactStore, ledger: EvidenceLedger):
    submission = build_submission(narrative=build_narrative(headline=""))
    assert "headline_missing" in _codes(_validate(submission, store, ledger))


def test_jargon_in_the_headline_flags_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = "The mixture shifts 2pp towards Spain after reweighting the injury scenario."
    submission = build_submission(narrative=build_narrative(headline=headline))
    report = _validate(submission, store, ledger)
    jargon = [i for i in report.issues if i.code == "headline_jargon"]
    assert jargon and all(i.severity == "copy" for i in jargon)


def test_rambling_headline_flags_as_copy(store: RunArtifactStore, ledger: EvidenceLedger):
    headline = (
        "Spain lead. England hold. France drift. Portugal rise. Brazil wobble. Italy fade. Croatia stall. Japan climb."
    )
    submission = build_submission(narrative=build_narrative(headline=headline))
    report = _validate(submission, store, ledger)
    too_long = [i for i in report.issues if i.code == "headline_too_long"]
    assert too_long and all(i.severity == "copy" for i in too_long)


@pytest.mark.parametrize(
    "headline",
    [
        "Spain are still favourites at about one in six. England's chances edge up with Saka back in training.",
        (
            "Spain remain the team to beat after another controlled win. England's chances edge up with Saka "
            "back in full training and no fresh injuries in camp. France drift slightly as Mbappe sits out "
            "again. The bookmakers broadly agree with this picture. Nothing else in today's news moves the "
            "big contenders."
        ),
        (
            "Spain remain the team to beat. England's chances edge up with Saka back. France drift as Mbappe "
            "sits out. Portugal hold their ground. The bookmakers broadly agree. Nothing else moves the big "
            "contenders today."
        ),
    ],
    ids=["two-sentences", "five-sentences-within-budget", "six-sentences-within-grace"],
)
def test_headline_within_the_softened_budget_passes(store: RunArtifactStore, ledger: EvidenceLedger, headline: str):
    submission = build_submission(narrative=build_narrative(headline=headline))
    assert not {code for code in _codes(_validate(submission, store, ledger)) if code.startswith("headline")}
