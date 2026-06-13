from __future__ import annotations

from pathlib import Path

import pytest

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission


def _submission() -> ForecastSubmission:
    return ForecastSubmission(
        artifact_id="mixture-001",
        narrative={
            "headline": "Spain stay favourites and England remain close behind after a quiet day of news.",
            "focus_story": "England trained in full; nothing moved.",
            "slot_rationales": {str(m): "rating gap" for m in range(73, 89)},
            "travel_memo": "East coast path holds.",
        },
        scenario_weights=[],
        evidence_ids=[],
    )


def _ledger(tmp_path: Path, *, busy: bool) -> EvidenceLedger:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    if busy:
        ledger.append(
            claim="Starter doubtful for the opener",
            source_url="https://example.com/a",
            status="probable",
            mechanism="key starter missing",
            team_id="england",
        )
    return ledger


@pytest.mark.parametrize(
    ("vs_floor", "busy", "fires"),
    [
        (1.0, True, True),
        (1.0, False, False),
        (1.3, True, False),
        (None, True, False),
    ],
)
def test_mixture_underdispersed_fires_softly_over_contested_evidence(tmp_path, vs_floor, busy, fires) -> None:
    report = validate_submission(
        _submission(),
        artifacts=None,
        ledger=_ledger(tmp_path, busy=busy),
        limits=ValidatorLimits(),
        focus_team="england",
        focus_vs_floor=vs_floor,
    )

    issue = next((i for i in report.issues if i.code == "mixture_underdispersed"), None)
    if fires:
        assert issue is not None
        assert issue.severity == "copy"
        assert "widen via a world" in issue.message
    else:
        assert issue is None
