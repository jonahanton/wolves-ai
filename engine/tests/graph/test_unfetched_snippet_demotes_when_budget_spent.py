from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.agent.source_memory import SourceMemory
from wolves.graph.agents import _demote_unfetchable_snippets
from wolves.graph.contracts import CandidateBranch, LedgerEvidence, ResearchOutput
from wolves.toolkit._budget_gate import BudgetGate

URL = "https://www.reuters.com/sports/soccer/france-training"


def _output() -> ResearchOutput:
    return ResearchOutput(
        summary="Availability note.",
        evidence=[
            LedgerEvidence(
                claim="A France forward returned to training",
                source_url=URL,
                quote="returned to training",
                status="probable",
                mechanism="availability",
                team_id="france",
            )
        ],
    )


@pytest.fixture
def deps(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.source_memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    yield deps
    deps.runtime.shutdown()


def test_unfetched_snippet_demotes_to_signal_once_budget_is_spent(deps):
    deps.gate = BudgetGate(budget=1)
    deps.gate.try_reserve()
    output = _output()

    _demote_unfetchable_snippets(output, deps)

    assert output.evidence == []
    assert any("returned to training" in signal for signal in output.signals)


def test_unfetched_snippet_is_kept_when_budget_remains(deps):
    deps.gate = BudgetGate(budget=12)
    output = _output()

    _demote_unfetchable_snippets(output, deps)

    assert len(output.evidence) == 1
    assert output.signals == []


def test_branch_referenced_evidence_is_never_demoted(deps):
    deps.gate = BudgetGate(budget=1)
    deps.gate.try_reserve()
    output = _output()
    output.candidate_branches = [
        CandidateBranch(
            branch_id="b1",
            hypothesis="forward returns",
            support="training report",
            collapse_condition="ruled out",
            suggested_quant_question="price the return",
            confidence="medium",
            evidence_indices=[1],
        )
    ]

    _demote_unfetchable_snippets(output, deps)

    assert len(output.evidence) == 1
    assert output.candidate_branches[0].evidence_indices == [1]
