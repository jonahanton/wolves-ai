from __future__ import annotations

from tests.graph.conftest import build_graph_deps
from wolves.agent.source_memory import SourceMemory
from wolves.graph.agents import _research_source_issues
from wolves.graph.contracts import LedgerEvidence, ResearchOutput


def test_non_official_lineup_cannot_be_confirmed():
    output = ResearchOutput(
        summary="England line-up reported.",
        evidence=[
            LedgerEvidence(
                claim="England confirms starting XI vs Croatia",
                source_url="https://cryptobriefing.com/england-starting-xi-world-cup-croatia/",
                quote="Here is the full starting XI.",
                status="confirmed",
                mechanism="lineup announcement",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output)


def test_official_lineup_confirmation_is_allowed():
    output = ResearchOutput(
        summary="England line-up confirmed.",
        evidence=[
            LedgerEvidence(
                claim="England confirms starting XI vs Croatia",
                source_url="https://www.fifa.com/en/match-centre/match/17/285023/289273/400021462",
                quote="Line-ups",
                status="confirmed",
                mechanism="lineup announcement",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output) == []


def test_federation_lineup_confirmation_is_allowed_for_non_england_team():
    output = ResearchOutput(
        summary="France line-up confirmed.",
        evidence=[
            LedgerEvidence(
                claim="France confirm their starting XI",
                source_url="https://www.fff.fr/article/france-starting-xi",
                quote="Le onze de depart.",
                status="confirmed",
                mechanism="lineup announcement",
                team_id="france",
            )
        ],
    )

    assert _research_source_issues(output) == []


def test_non_lineup_injury_claim_can_be_confirmed_from_news():
    output = ResearchOutput(
        summary="Saka load management note.",
        evidence=[
            LedgerEvidence(
                claim="Bukayo Saka is nursing an Achilles problem",
                source_url="https://www.espn.com/soccer/story/_/id/48701061/england-world-cup-2026",
                quote="Saka is still nursing an Achilles problem.",
                status="confirmed",
                mechanism="injury management",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output) == []


def test_public_evidence_must_be_fetched_this_run(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.source_memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    output = ResearchOutput(
        summary="Availability note.",
        evidence=[
            LedgerEvidence(
                claim="A France forward returned to training",
                source_url="https://www.reuters.com/sports/soccer/france-training",
                quote="returned to training",
                status="confirmed",
                mechanism="availability",
                team_id="france",
            )
        ],
    )

    [issue] = _research_source_issues(output, deps)

    assert "without fetching" in issue
    deps.runtime.shutdown()


def test_fetched_public_evidence_passes_source_discipline(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.source_memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    url = "https://www.reuters.com/sports/soccer/france-training"
    deps.source_memory.record(url, run_id=deps.runtime.run_id, disposition="fetched")
    output = ResearchOutput(
        summary="Availability note.",
        evidence=[
            LedgerEvidence(
                claim="A France forward returned to training",
                source_url=url,
                quote="returned to training",
                status="confirmed",
                mechanism="availability",
                team_id="france",
            )
        ],
    )

    assert _research_source_issues(output, deps) == []
    deps.runtime.shutdown()


def test_first_party_tool_claims_need_internal_source_urls():
    output = ResearchOutput(
        summary="Markets fetched.",
        evidence=[
            LedgerEvidence(
                claim="England market consensus is 10.3%",
                source_url="https://www.get_odds",
                quote="england: 0.103",
                status="confirmed",
                mechanism="market consensus",
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output)
    assert "fake web URL" in issue
    assert "internal://get_odds" in issue


def test_first_party_tool_claims_need_canonical_internal_urls():
    output = ResearchOutput(
        summary="Markets fetched.",
        evidence=[
            LedgerEvidence(
                claim="England market consensus is 10.3%",
                source_url="internal:get_odds",
                quote="england: 0.103",
                status="confirmed",
                mechanism="market consensus",
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output)
    assert "non-canonical internal source" in issue


def test_canonical_internal_tool_urls_are_allowed():
    output = ResearchOutput(
        summary="Markets fetched.",
        evidence=[
            LedgerEvidence(
                claim="England market consensus is 10.3%",
                source_url="internal://get_odds",
                quote="england: 0.103",
                status="confirmed",
                mechanism="market consensus",
                team_id="england",
            ),
            LedgerEvidence(
                claim="England play Croatia on 17 June",
                source_url="internal://get_results_and_fixtures",
                quote="England v Croatia, 2026-06-17",
                status="confirmed",
                mechanism="fixture context",
                team_id="england",
            ),
        ],
    )

    assert _research_source_issues(output) == []


def test_placeholder_urls_are_rejected():
    output = ResearchOutput(
        summary="Placeholder source.",
        evidence=[
            LedgerEvidence(
                claim="England trained normally",
                source_url="https://example.com/england",
                quote="England trained normally.",
                status="probable",
                mechanism="availability",
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output)
    assert "placeholder URL" in issue


def test_proposed_delta_uses_strength_units():
    output = ResearchOutput(
        summary="Elo-scale delta.",
        evidence=[
            LedgerEvidence(
                claim="England lose a starter",
                source_url="https://www.reuters.com/sports/soccer/england",
                quote="A starter is out.",
                status="confirmed",
                mechanism="availability",
                proposed_delta=-15.0,
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output)
    assert "model-strength units" in issue


def test_group_claims_match_the_tournament_format(tmp_path):
    deps = build_graph_deps(tmp_path)
    output = ResearchOutput(
        summary="Wrong group.",
        evidence=[
            LedgerEvidence(
                claim="England remain in Group A contention",
                source_url="https://www.reuters.com/sports/soccer/england",
                quote="England are in Group A.",
                status="probable",
                mechanism="group state",
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output, deps)
    assert "group A" in issue
    assert "group L" in issue
    deps.runtime.shutdown()


def test_summary_group_context_must_match_the_tournament_format(tmp_path):
    deps = build_graph_deps(tmp_path)
    output = ResearchOutput(
        summary="Haiti 0-1 Scotland (Group J) is already settled.",
        evidence=[],
        signals=["Australia 1-0 Türkiye (Group K) shaped the table."],
    )

    issues = _research_source_issues(output, deps)

    assert any("haiti is group C" in issue for issue in issues)
    assert any("scotland is group C" in issue for issue in issues)
    assert any("australia is group D" in issue for issue in issues)
    assert any("turkiye is group D" in issue for issue in issues)
    deps.runtime.shutdown()


def test_summary_group_context_handles_comma_separated_result_lists(tmp_path):
    deps = build_graph_deps(tmp_path)
    output = ResearchOutput(
        summary="Non-England results: Haiti 0-1 Scotland (Group C), Australia 2-0 Türkiye (Group D).",
        evidence=[],
    )

    assert _research_source_issues(output, deps) == []
    deps.runtime.shutdown()
