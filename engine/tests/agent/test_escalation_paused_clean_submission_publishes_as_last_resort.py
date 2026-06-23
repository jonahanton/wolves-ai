from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.agent.deps import SubmissionState
from wolves.agent.tools.submission import submit_forecast
from wolves.agent.validator import ValidationReport
from wolves.graph.runner import GraphRunResult
from wolves.run_agent import _prefer_last_clean, _should_publish_fallback

ESCALATIONS = ["england +3.00pp vs baseline (threshold 2.00pp)"]


async def test_escalation_pause_stashes_the_clean_submission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deps = build_graph_deps(tmp_path)
    submission = build_submission()
    report = ValidationReport(ok=True, escalations=ESCALATIONS)
    monkeypatch.setattr(submit_forecast, "validation_report", lambda args, deps: report)

    result = await submit_forecast._submit_forecast(submission, deps)
    deps.runtime.shutdown()

    assert result.ok and result.payload["accepted"] is False
    assert deps.submission.accepted is None
    assert deps.submission.last_clean == submission
    assert deps.submission.last_clean_escalations == ESCALATIONS


def test_interrupted_steelman_publishes_the_last_clean_submission():
    submission = build_submission()
    state = SubmissionState(last_clean=submission, last_clean_escalations=ESCALATIONS)

    result = _prefer_last_clean(GraphRunResult(submission=None), state, run_id="run-1", referee_enabled=True)

    assert result.submission == submission
    assert result.escalations == ESCALATIONS
    assert state.referee_status == "bypassed_interrupted"


def test_referee_intervention_alone_keeps_last_clean_fallback_available():
    submission = build_submission()
    state = SubmissionState(
        last_clean=submission,
        last_clean_escalations=ESCALATIONS,
        referee_interventions=1,
    )

    result = _prefer_last_clean(GraphRunResult(submission=None), state, run_id="run-1", referee_enabled=True)

    assert result.submission == submission


def test_prior_referee_approval_does_not_cover_a_replacement_submission():
    prior = build_submission()
    replacement = build_submission(artifact_id="mixture-002")
    state = SubmissionState(
        last_clean=replacement,
        referee_status="approved",
        referee_approved={hashlib.sha256(prior.model_dump_json().encode("utf-8")).hexdigest()[:16]},
    )

    result = _prefer_last_clean(GraphRunResult(submission=None), state, run_id="run-1", referee_enabled=True)

    assert result.submission == replacement
    assert state.referee_status == "bypassed_interrupted"


def test_referee_publication_block_blocks_last_clean_and_fallback():
    submission = build_submission()
    state = SubmissionState(
        last_clean=submission,
        last_clean_escalations=ESCALATIONS,
        publication_blocked=True,
    )

    result = _prefer_last_clean(GraphRunResult(submission=None), state, run_id="run-1", referee_enabled=True)

    assert result.submission is None
    assert not _should_publish_fallback(state)


def test_nothing_clean_still_falls_through_to_the_fallback():
    result = _prefer_last_clean(
        GraphRunResult(submission=None), SubmissionState(), run_id="run-1", referee_enabled=True
    )
    assert result.submission is None
