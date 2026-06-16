from __future__ import annotations

from pathlib import Path

import pytest

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.validator import ValidatorLimits, validate_submission


def _submission(rationale: str) -> ForecastSubmission:
    return ForecastSubmission(
        artifact_id="mixture-001",
        narrative={"headline": "Spain stay favourites after a quiet day of news."},
        revision_rationale=rationale,
    )


@pytest.mark.parametrize(
    ("revisions_used", "rationale", "fires"),
    [
        (1, "", True),
        (1, "  ", True),
        (1, "Pre-mortem surfaced no earned edge, so France was widened not moved.", False),
        (0, "", False),
    ],
)
def test_revision_rationale_required_when_revised(tmp_path: Path, revisions_used, rationale, fires) -> None:
    report = validate_submission(
        _submission(rationale),
        artifacts=None,
        ledger=EvidenceLedger(tmp_path / "ledger.jsonl"),
        limits=ValidatorLimits(),
        revisions_used=revisions_used,
    )

    issue = next((i for i in report.issues if i.code == "revision_rationale_missing"), None)
    if fires:
        assert issue is not None
        assert issue.severity == "copy"
    else:
        assert issue is None
