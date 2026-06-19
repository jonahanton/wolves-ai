from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.graph.agents import _research_source_issues
from wolves.graph.contracts import LedgerEvidence, ResearchOutput
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
