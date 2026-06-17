"""Near-duplicate worlds that split a directional vote are flagged for merge;
genuinely opposing or distinct worlds are not."""

from __future__ import annotations

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.mixture_hygiene import describe_signature, diluted_groups, world_signature
from wolves.agent.validator import ValidatorLimits, validate_submission


def _strength(team: str, mean: float) -> dict:
    return {"type": "strength", "team": team, "delta": {"mean": mean, "sd": 0.04}, "reason": "test"}


def test_two_same_direction_spain_worlds_share_a_signature():
    a = world_signature([_strength("spain", 0.09)])
    b = world_signature([_strength("spain", 0.05)])
    assert a == b


def test_opposing_spain_worlds_do_not_share_a_signature():
    up = world_signature([_strength("spain", 0.09)])
    down = world_signature([_strength("spain", -0.09)])
    assert up != down


@pytest.mark.parametrize(
    ("worlds", "expected"),
    [
        # Split optimistic vote above the threshold: flagged.
        (
            {
                "spain_returns": (0.3, [_strength("spain", 0.09)]),
                "spain_depth": (0.3, [_strength("spain", 0.06)]),
                "spain_doubt": (0.4, [_strength("spain", -0.08)]),
            },
            [(["spain_depth", "spain_returns"], 0.6)],
        ),
        # Stories on different teams never collide.
        (
            {
                "spain": (0.5, [_strength("spain", 0.09)]),
                "france": (0.5, [_strength("france", 0.09)]),
            },
            [],
        ),
        # A duplicated pair below the combined-weight floor stays quiet.
        (
            {
                "spain_a": (0.05, [_strength("spain", 0.09)]),
                "spain_b": (0.05, [_strength("spain", 0.07)]),
                "base": (0.9, []),
            },
            [],
        ),
    ],
)
def test_diluted_groups(worlds, expected):
    assert diluted_groups(worlds, min_combined_weight=0.25) == expected


def test_signature_description_names_the_shared_direction():
    signature = world_signature([_strength("spain", 0.09), _strength("france", -0.04)])

    assert describe_signature(signature) == "strength:france down, strength:spain up"


def test_validator_treats_weight_dilution_as_hard_artifact_issue(tmp_path):
    store = build_run_store(tmp_path)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="split market view",
        payload={
            "weights": {"market_a": 0.35, "market_b": 0.35, "model": 0.3},
            "worlds": {
                "market_a": {"perturbations": [_strength("spain", 0.09), _strength("france", -0.04)]},
                "market_b": {"perturbations": [_strength("spain", 0.06), _strength("france", -0.02)]},
                "model": {"perturbations": []},
            },
            "mixture": {"spain": 0.17, "france": 0.1, "rest": 0.73},
        },
    )
    submission = build_submission(
        evidence_ids=[],
        scenario_weights=[
            {"name": "market_a", "weight": 0.35, "rationale": "First market view."},
            {"name": "market_b", "weight": 0.35, "rationale": "Second market view."},
            {"name": "model", "weight": 0.3, "rationale": "Model view."},
        ],
    )

    report = validate_submission(submission, artifacts=store, ledger=ledger, limits=ValidatorLimits())

    issue = next(issue for issue in report.issues if issue.code == "weight_dilution")
    assert issue.severity == "hard"
    assert "artifact structure issue" in issue.message
    assert "market_a and market_b" in issue.message
    assert "strength:spain up" in issue.message
