from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_narrative, build_submission
from tests.graph.conftest import build_run_store
from wolves.agent.knockout_slots import open_knockout_rationale_slots, slot_rationale_keys
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission
from wolves.sim.format import FormatData, KnockoutMatch, PlayedResult


@pytest.fixture
def ledger(tmp_path: Path) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="Team news confirmed",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="availability",
        team_id="england",
    )
    return ledger


def _format() -> FormatData:
    return FormatData(
        teams=[],
        group_matches=[],
        venues=[],
        knockout=[
            KnockoutMatch(match=73, stage="r32", date="2026-06-28", city="Los Angeles", home="1A", away="3:CDEF"),
            KnockoutMatch(match=74, stage="r32", date="2026-06-28", city="Boston", home="1B", away="3:EFGH"),
            KnockoutMatch(match=89, stage="r16", date="2026-07-04", city="New York", home="W73", away="W74"),
            KnockoutMatch(match=90, stage="r16", date="2026-07-04", city="Dallas", home="W75", away="W76"),
        ],
    )


def _played(*matches: int) -> dict[int, PlayedResult]:
    return {match: PlayedResult(match=match, home_goals=1, away_goals=0, winner="alpha") for match in matches}


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_open_slots_stay_on_r32_until_the_round_is_resolved() -> None:
    slots = open_knockout_rationale_slots(_format(), _played(73))

    assert [slot.key for slot in slots] == ["74"]


def test_open_slots_move_to_r16_after_r32_is_resolved() -> None:
    slots = open_knockout_rationale_slots(_format(), _played(73, 74))

    assert [slot.key for slot in slots] == ["89", "90"]


def test_validator_accepts_rationales_for_the_current_knockout_layer(tmp_path: Path, ledger: EvidenceLedger) -> None:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="accepted mixture",
        payload={
            "weights": {"market": 1.0},
            "worlds": {"market": {"perturbations": []}},
            "mixture": {"england": 0.08, "spain": 0.18, "rest": 0.74},
        },
    )
    keys = slot_rationale_keys(open_knockout_rationale_slots(_format(), _played(73, 74)))
    narrative = build_narrative(
        slot_rationales={key: f"Slot {key}: the likely winner has the cleaner path." for key in keys}
    )
    submission = build_submission(narrative=narrative)

    report = validate_submission(
        submission,
        artifacts=store,
        ledger=ledger,
        limits=ValidatorLimits(),
        slot_rationale_keys=keys,
    )

    assert "slot_rationales_incomplete" not in _codes(report)


def test_validator_rejects_played_round_rationales(tmp_path: Path, ledger: EvidenceLedger) -> None:
    store = build_run_store(tmp_path)
    store.add(
        kind="mixture",
        created_by="quant-1",
        summary="accepted mixture",
        payload={
            "weights": {"market": 1.0},
            "worlds": {"market": {"perturbations": []}},
            "mixture": {"england": 0.08, "spain": 0.18, "rest": 0.74},
        },
    )
    keys = slot_rationale_keys(open_knockout_rationale_slots(_format(), _played(73, 74)))
    narrative = build_narrative(slot_rationales={"73": "Slot 73 is over.", "89": "Slot 89 remains live."})
    submission = build_submission(narrative=narrative)

    report = validate_submission(
        submission,
        artifacts=store,
        ledger=ledger,
        limits=ValidatorLimits(),
        slot_rationale_keys=keys,
    )

    assert "slot_rationales_incomplete" in _codes(report)
    assert "missing 90" in report.summary()
    assert "unexpected 73" in report.summary()
