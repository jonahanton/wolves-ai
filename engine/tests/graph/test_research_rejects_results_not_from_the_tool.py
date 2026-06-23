from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.graph.agents import _research_source_issues, _sanitise_deterministic_research
from wolves.graph.contracts import CandidateBranch, LedgerEvidence, ResearchOutput
from wolves.sim.format import PlayedResult


class _StubForecaster:
    def __init__(self, played: dict[int, PlayedResult]) -> None:
        self._played = played

    def played_results(self, *, extra_results: dict[int, PlayedResult] | None = None) -> dict[int, PlayedResult]:
        return self._played | (extra_results or {})


def _deps(tmp_path: Path, played: dict[int, PlayedResult]):
    return dataclasses.replace(build_graph_deps(tmp_path), forecaster=_StubForecaster(played))


def _evidence(claim: str, *, source: str = "internal://get_results_and_fixtures") -> ResearchOutput:
    return ResearchOutput(
        summary="research",
        evidence=[LedgerEvidence(claim=claim, source_url=source, quote="", status="confirmed", mechanism="")],
    )


def test_scoreline_for_an_unplayed_fixture_trips(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = _evidence("Brazil 0-1 Haiti in Group C, confirmed result")
    assert any("has not been played" in issue for issue in _research_source_issues(output, deps))


def test_scoreline_for_a_finished_fixture_passes(tmp_path: Path):
    deps = _deps(tmp_path, played={7: PlayedResult(match=7, home_goals=1, away_goals=1)})
    output = _evidence("Brazil 1-1 Morocco, full time")
    assert _research_source_issues(output, deps) == []


def test_future_fixture_without_a_scoreline_passes(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = _evidence("Brazil vs Haiti is yet to kick off on 2026-06-20; Neymar absent")
    assert _research_source_issues(output, deps) == []


def test_iso_date_between_two_teams_is_not_read_as_a_score(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = _evidence("Brazil meet Haiti on 2026-06-20 in Philadelphia; preview only")
    assert _research_source_issues(output, deps) == []


def test_missing_forecaster_skips_the_check(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    output = _evidence("Brazil 0-1 Haiti in Group C, confirmed result")
    assert _research_source_issues(output, deps) == []


def test_unplayed_result_is_removed_without_losing_valid_evidence(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = ResearchOutput(
        summary="research",
        evidence=[
            LedgerEvidence(
                claim="Brazil 0-1 Haiti, full time",
                source_url="internal://get_results_and_fixtures",
            ),
            LedgerEvidence(claim="Neymar trained", source_url="internal://get_results_and_fixtures"),
        ],
        candidate_branches=[
            CandidateBranch(
                branch_id="false-result",
                hypothesis="Brazil lost",
                support="scoreline",
                collapse_condition="not finished",
                evidence_indices=[1],
                confidence="medium",
                suggested_quant_question="Price it",
            )
        ],
    )

    _sanitise_deterministic_research(output, deps)

    assert [item.claim for item in output.evidence] == ["Neymar trained"]
    assert output.candidate_branches == []


def test_multiple_group_mentions_are_not_rewritten_ambiguously(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = ResearchOutput(
        summary="research",
        evidence=[
            LedgerEvidence(
                claim="Brazil are in Group C while France are in Group I.",
                source_url="internal://get_results_and_fixtures",
                team_id="brazil",
            )
        ],
    )

    _sanitise_deterministic_research(output, deps)

    assert output.evidence[0].claim == "Brazil are in Group C while France are in Group I."


def test_source_quote_is_never_rewritten(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = ResearchOutput(
        summary="research",
        evidence=[
            LedgerEvidence(
                claim="France group assignment",
                quote="France are in Group A.",
                source_url="https://example.com/report",
                team_id="france",
            )
        ],
    )

    _sanitise_deterministic_research(output, deps)

    assert output.evidence[0].quote == "France are in Group A."


def test_historical_web_result_is_not_removed(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = _evidence("Brazil 1-0 Morocco at the 1986 World Cup", source="https://example.com/history")

    _sanitise_deterministic_research(output, deps)

    assert len(output.evidence) == 1


def test_branch_keeps_surviving_receipt_after_unplayed_result_is_removed(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = ResearchOutput(
        summary="research",
        evidence=[
            LedgerEvidence(
                claim="Brazil 0-1 Haiti, full time",
                source_url="internal://get_results_and_fixtures",
            ),
            LedgerEvidence(claim="Neymar trained", source_url="internal://get_results_and_fixtures"),
        ],
        candidate_branches=[
            CandidateBranch(
                branch_id="availability",
                hypothesis="Brazil availability changes",
                support="training and result",
                collapse_condition="training status settles",
                evidence_indices=[1, 2],
                confidence="medium",
                suggested_quant_question="Price it",
            )
        ],
    )

    _sanitise_deterministic_research(output, deps)

    assert output.candidate_branches[0].evidence_indices == [1]


def test_source_id_only_branch_survives_unrelated_evidence_removal(tmp_path: Path):
    deps = _deps(tmp_path, played={})
    output = ResearchOutput(
        summary="research",
        evidence=[
            LedgerEvidence(
                claim="Brazil 0-1 Haiti, full time",
                source_url="internal://get_results_and_fixtures",
            )
        ],
        candidate_branches=[
            CandidateBranch(
                branch_id="existing-availability",
                hypothesis="Availability remains uncertain",
                support="Existing ledger evidence",
                collapse_condition="Squad confirmation",
                source_ids=["ledger-existing"],
                confidence="medium",
                suggested_quant_question="Price it",
            )
        ],
    )

    _sanitise_deterministic_research(output, deps)

    assert [branch.branch_id for branch in output.candidate_branches] == ["existing-availability"]
