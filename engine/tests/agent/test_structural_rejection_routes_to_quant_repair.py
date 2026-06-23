from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission.structural_repair import structural_repair_result
from wolves.agent.validator import ValidationIssue, ValidationReport


def _report(*codes: str) -> ValidationReport:
    return ValidationReport(ok=False, issues=[ValidationIssue(code=code, message=code) for code in codes])


@pytest.fixture
def deps(tmp_path: Path) -> AgentDeps:
    deps = build_graph_deps(tmp_path)
    yield deps
    deps.runtime.shutdown()


def test_quant_owned_failure_routes_once_without_spending_a_retry(deps: AgentDeps):
    result = structural_repair_result(_report("factor_audit_missing_coverage"), deps, artifact_id="mixture-002")

    assert result is not None
    assert result.error.type == "structural_repair_required"
    assert deps.submission.structural_repair_required is True
    assert deps.submission.validation_failures == 0


def test_same_signature_repeat_falls_through_to_hard_path(deps: AgentDeps):
    report = _report("factor_audit_missing_coverage")
    assert structural_repair_result(report, deps, artifact_id="mixture-002") is not None
    deps.submission.structural_repair_required = False

    assert structural_repair_result(report, deps, artifact_id="mixture-002") is None


def test_forecast_owned_failure_is_not_routed(deps: AgentDeps):
    assert structural_repair_result(_report("rank_claim_mismatch"), deps, artifact_id="mixture-002") is None


def test_distinct_signatures_stop_routing_at_the_attempt_cap(deps: AgentDeps):
    deps.submission.structural_repair_attempts = deps.settings.agent_structural_repair_attempts

    assert structural_repair_result(_report("factor_audit_missing_coverage"), deps, artifact_id="mixture-009") is None
