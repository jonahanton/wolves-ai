from __future__ import annotations

from tests.graph.conftest import build_graph_deps
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
